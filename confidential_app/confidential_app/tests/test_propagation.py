import frappe
from frappe.tests.utils import FrappeTestCase
from confidential_app.confidential_app.utils.validations import (
	set_stock_entry_confidentiality,
	set_work_order_confidentiality,
	_copy_access_lists,
)


class TestConfidentialPropagation(FrappeTestCase):
	"""Integration tests for confidentiality propagation from BOM to Stock Entry and Work Order."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._ensure_roles()
		cls._create_test_items()
		cls._enable_protection()
		cls.company = frappe.defaults.get_defaults().get("company")

	@classmethod
	def _ensure_roles(cls):
		for role_name in ("Confidential Manager", "Confidential User"):
			if not frappe.db.exists("Role", role_name):
				frappe.get_doc({
					"doctype": "Role",
					"role_name": role_name,
					"desk_access": 1,
				}).insert(ignore_permissions=True)

	@classmethod
	def _create_test_items(cls):
		for item_code in ("PROP_ITEM_A", "PROP_ITEM_B"):
			if not frappe.db.exists("Item", item_code):
				frappe.get_doc({
					"doctype": "Item",
					"item_code": item_code,
					"item_name": item_code,
					"item_group": "Products",
					"stock_uom": "Nos",
				}).insert(ignore_permissions=True)

	@classmethod
	def _enable_protection(cls):
		settings = frappe.get_single("Confidential Settings")
		settings.enable_confidential_protection = 1
		settings.protect_bom = 1
		settings.protect_stock_entry = 1
		settings.protect_work_order = 1
		settings.enable_audit_trail = 0
		settings.enable_access_notifications = 0
		settings.save(ignore_permissions=True)
		frappe.db.commit()

	def _create_bom(self, confidential=True, roles=None, users=None):
		bom = frappe.get_doc({
			"doctype": "BOM",
			"item": "PROP_ITEM_A",
			"quantity": 1,
			"is_active": 1,
			"is_confidential": 1 if confidential else 0,
			"items": [{"item_code": "PROP_ITEM_B", "qty": 1, "uom": "Nos", "rate": 100}],
		})
		if confidential:
			for role in (roles or ["Confidential Manager"]):
				bom.append("allowed_roles", {"role": role})
			for user_email in (users or []):
				bom.append("allowed_users", {"user": user_email})
		bom.insert(ignore_permissions=True)
		frappe.db.commit()
		return bom

	# -----------------------------------------------------------------------
	# set_stock_entry_confidentiality (before_insert hook)
	# -----------------------------------------------------------------------

	def test_se_inherits_confidentiality(self):
		"""Stock Entry inherits is_confidential and allowed_roles from BOM."""
		bom = self._create_bom(confidential=True, roles=["Confidential Manager"])

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.bom_no = bom.name

		set_stock_entry_confidentiality(se)

		self.assertEqual(se.is_confidential, 1)
		se_roles = {d.role for d in se.get("allowed_roles", [])}
		self.assertIn("Confidential Manager", se_roles)

	def test_se_inherits_allowed_users(self):
		"""Stock Entry inherits allowed_users from BOM."""
		user_email = "prop_test_user@test.local"
		if not frappe.db.exists("User", user_email):
			frappe.get_doc({
				"doctype": "User",
				"email": user_email,
				"first_name": "PropTest",
				"send_welcome_email": 0,
				"roles": [{"role": "Manufacturing User"}, {"role": "Stock User"}],
			}).insert(ignore_permissions=True)

		bom = self._create_bom(confidential=True, users=[user_email])

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.bom_no = bom.name

		set_stock_entry_confidentiality(se)

		se_users = {d.user for d in se.get("allowed_users", [])}
		self.assertIn(user_email, se_users)

	def test_se_non_confidential_bom(self):
		"""Stock Entry is not marked confidential when BOM isn't."""
		bom = self._create_bom(confidential=False)

		se = frappe.new_doc("Stock Entry")
		se.purpose = "Manufacture"
		se.bom_no = bom.name

		set_stock_entry_confidentiality(se)

		self.assertEqual(se.is_confidential, 0)

	# -----------------------------------------------------------------------
	# set_work_order_confidentiality (before_insert hook)
	# -----------------------------------------------------------------------

	def test_wo_inherits_confidentiality(self):
		"""Work Order inherits confidentiality from BOM."""
		bom = self._create_bom(confidential=True, roles=["Confidential Manager", "Confidential User"])

		wo = frappe.new_doc("Work Order")
		wo.production_item = "PROP_ITEM_A"
		wo.bom_no = bom.name
		wo.qty = 1
		wo.company = self.company

		set_work_order_confidentiality(wo)

		self.assertEqual(wo.is_confidential, 1)
		wo_roles = {d.role for d in wo.get("allowed_roles", [])}
		self.assertIn("Confidential Manager", wo_roles)
		self.assertIn("Confidential User", wo_roles)

	# -----------------------------------------------------------------------
	# _copy_access_lists helper
	# -----------------------------------------------------------------------

	def test_copy_access_lists(self):
		"""_copy_access_lists copies both roles and users."""
		from frappe.utils import today, add_days

		bom = self._create_bom(confidential=True, roles=["Confidential Manager"])
		bom.append("allowed_users", {
			"user": "Administrator",
			"valid_from": today(),
			"valid_until": add_days(today(), 30),
		})
		bom.flags.ignore_permissions = True
		bom.save()
		frappe.db.commit()

		target = frappe.new_doc("Stock Entry")
		_copy_access_lists(bom, target)

		target_roles = {d.role for d in target.get("allowed_roles", [])}
		self.assertIn("Confidential Manager", target_roles)

		target_users = {d.user for d in target.get("allowed_users", [])}
		self.assertIn("Administrator", target_users)

	# -----------------------------------------------------------------------
	# BOM change cascading
	# -----------------------------------------------------------------------

	def test_bom_role_change_cascades_to_linked_stock_entries(self):
		"""When BOM roles change, linked draft Stock Entries update too."""
		bom = self._create_bom(confidential=True, roles=["Confidential Manager"])

		# Create a Stock Entry directly via DB to avoid ERPNext stock validation
		se_name = frappe.generate_hash(length=10)
		frappe.db.sql("""
			INSERT INTO `tabStock Entry`
			(name, docstatus, purpose, bom_no, company, is_confidential, owner, modified_by, creation, modified)
			VALUES (%s, 0, 'Manufacture', %s, %s, 1, 'Administrator', 'Administrator', NOW(), NOW())
		""", (se_name, bom.name, self.company))
		frappe.db.sql("""
			INSERT INTO `tabConfidential Role Mapping`
			(name, parent, parenttype, parentfield, role, owner, modified_by, creation, modified)
			VALUES (%s, %s, 'Stock Entry', 'allowed_roles', 'Confidential Manager',
					'Administrator', 'Administrator', NOW(), NOW())
		""", (frappe.generate_hash(length=10), se_name))
		frappe.db.commit()

		# Now update BOM to add another role
		bom.reload()
		bom.append("allowed_roles", {"role": "Confidential User"})
		bom.flags.ignore_permissions = True
		bom.save()
		frappe.db.commit()

		# Check that the Stock Entry was updated
		se = frappe.get_doc("Stock Entry", se_name)
		se_roles = {d.role for d in se.get("allowed_roles", [])}
		self.assertIn("Confidential User", se_roles)

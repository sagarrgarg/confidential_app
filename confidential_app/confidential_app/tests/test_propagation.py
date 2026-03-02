import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today


class TestConfidentialPropagation(FrappeTestCase):
	"""Integration tests for confidentiality propagation from BOM to Stock Entry and Work Order."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._ensure_roles()
		cls._create_test_items()
		cls._enable_protection()

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
	# Stock Entry propagation
	# -----------------------------------------------------------------------

	def test_stock_entry_inherits_confidentiality_from_bom(self):
		bom = self._create_bom(confidential=True, roles=["Confidential Manager"])

		se = frappe.get_doc({
			"doctype": "Stock Entry",
			"purpose": "Manufacture",
			"bom_no": bom.name,
			"fg_completed_qty": 1,
			"items": [{
				"item_code": "PROP_ITEM_B",
				"qty": 1,
				"uom": "Nos",
				"s_warehouse": "",
				"t_warehouse": "",
			}],
		})
		se.insert(ignore_permissions=True)
		frappe.db.commit()

		self.assertEqual(se.is_confidential, 1)
		se_roles = {d.role for d in se.get("allowed_roles", [])}
		self.assertIn("Confidential Manager", se_roles)

	def test_stock_entry_inherits_allowed_users(self):
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

		se = frappe.get_doc({
			"doctype": "Stock Entry",
			"purpose": "Manufacture",
			"bom_no": bom.name,
			"fg_completed_qty": 1,
			"items": [{
				"item_code": "PROP_ITEM_B",
				"qty": 1,
				"uom": "Nos",
				"s_warehouse": "",
				"t_warehouse": "",
			}],
		})
		se.insert(ignore_permissions=True)
		frappe.db.commit()

		se_users = {d.user for d in se.get("allowed_users", [])}
		self.assertIn(user_email, se_users)

	def test_non_confidential_bom_no_propagation(self):
		bom = self._create_bom(confidential=False)

		se = frappe.get_doc({
			"doctype": "Stock Entry",
			"purpose": "Manufacture",
			"bom_no": bom.name,
			"fg_completed_qty": 1,
			"items": [{
				"item_code": "PROP_ITEM_B",
				"qty": 1,
				"uom": "Nos",
			}],
		})
		se.insert(ignore_permissions=True)
		frappe.db.commit()

		self.assertEqual(se.is_confidential, 0)

	# -----------------------------------------------------------------------
	# Work Order propagation
	# -----------------------------------------------------------------------

	def test_work_order_inherits_confidentiality_from_bom(self):
		bom = self._create_bom(confidential=True, roles=["Confidential Manager", "Confidential User"])

		wo = frappe.get_doc({
			"doctype": "Work Order",
			"production_item": "PROP_ITEM_A",
			"bom_no": bom.name,
			"qty": 1,
			"company": frappe.defaults.get_defaults().get("company"),
		})
		wo.insert(ignore_permissions=True)
		frappe.db.commit()

		self.assertEqual(wo.is_confidential, 1)
		wo_roles = {d.role for d in wo.get("allowed_roles", [])}
		self.assertIn("Confidential Manager", wo_roles)
		self.assertIn("Confidential User", wo_roles)

	# -----------------------------------------------------------------------
	# BOM change cascading
	# -----------------------------------------------------------------------

	def test_bom_role_change_cascades_to_stock_entries(self):
		bom = self._create_bom(confidential=True, roles=["Confidential Manager"])
		bom.submit()
		frappe.db.commit()

		se = frappe.get_doc({
			"doctype": "Stock Entry",
			"purpose": "Manufacture",
			"bom_no": bom.name,
			"fg_completed_qty": 1,
			"items": [{
				"item_code": "PROP_ITEM_B",
				"qty": 1,
				"uom": "Nos",
			}],
		})
		se.insert(ignore_permissions=True)
		frappe.db.commit()

		bom.reload()
		bom.append("allowed_roles", {"role": "Confidential User"})
		bom.flags.ignore_permissions = True
		bom.save()
		frappe.db.commit()

		se.reload()
		se_roles = {d.role for d in se.get("allowed_roles", [])}
		self.assertIn("Confidential User", se_roles)

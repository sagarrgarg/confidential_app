import frappe
from frappe.tests.utils import FrappeTestCase
from confidential_app.confidential_app.utils.permissions import (
	_user_has_doc_access,
	_check_sub_bom_confidentiality,
	has_bom_permission,
	has_stock_entry_permission,
	has_work_order_permission,
	check_bom_permission,
	get_bom_permission_query_conditions,
)


class TestConfidentialPermissions(FrappeTestCase):
	"""Unit tests for the core permission-checking logic."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._ensure_roles()
		cls._create_test_users()
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
	def _create_test_users(cls):
		cls.manager_user = cls._ensure_user(
			"conf_manager@test.local", ["Confidential Manager", "Manufacturing Manager",
			"Manufacturing User", "Stock Manager", "Stock User"]
		)
		cls.regular_user = cls._ensure_user(
			"conf_regular@test.local", ["Manufacturing User", "Stock User"]
		)
		cls.conf_user = cls._ensure_user(
			"conf_user@test.local", ["Confidential User", "Manufacturing User", "Stock User"]
		)

	@classmethod
	def _ensure_user(cls, email, roles):
		if not frappe.db.exists("User", email):
			user = frappe.get_doc({
				"doctype": "User",
				"email": email,
				"first_name": email.split("@")[0],
				"send_welcome_email": 0,
			})
			for role in roles:
				user.append("roles", {"role": role})
			user.insert(ignore_permissions=True)
		return email

	@classmethod
	def _create_test_items(cls):
		for item_code in ("CONF_TEST_ITEM_A", "CONF_TEST_ITEM_B", "CONF_TEST_ITEM_C"):
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
		settings.enable_audit_trail = 1
		settings.enable_access_notifications = 0
		settings.save(ignore_permissions=True)
		frappe.db.commit()

	def _create_confidential_bom(self, item="CONF_TEST_ITEM_A", sub_item="CONF_TEST_ITEM_B",
								  roles=None, users=None):
		"""Helper to create a confidential BOM."""
		bom = frappe.get_doc({
			"doctype": "BOM",
			"item": item,
			"quantity": 1,
			"is_active": 1,
			"is_confidential": 1,
			"items": [{"item_code": sub_item, "qty": 1, "uom": "Nos", "rate": 100}],
		})
		for role in (roles or ["Confidential Manager"]):
			bom.append("allowed_roles", {"role": role})
		for user_email in (users or []):
			bom.append("allowed_users", {"user": user_email})
		bom.insert(ignore_permissions=True)
		frappe.db.commit()
		return bom

	def _create_non_confidential_bom(self, item="CONF_TEST_ITEM_A", sub_item="CONF_TEST_ITEM_B"):
		bom = frappe.get_doc({
			"doctype": "BOM",
			"item": item,
			"quantity": 1,
			"is_active": 1,
			"is_confidential": 0,
			"items": [{"item_code": sub_item, "qty": 1, "uom": "Nos", "rate": 100}],
		})
		bom.insert(ignore_permissions=True)
		frappe.db.commit()
		return bom

	# -----------------------------------------------------------------------
	# Role-based access
	# -----------------------------------------------------------------------

	def test_admin_always_has_access(self):
		bom = self._create_confidential_bom()
		result = has_bom_permission(bom, user="Administrator")
		self.assertTrue(result)

	def test_manager_role_has_access(self):
		bom = self._create_confidential_bom(roles=["Confidential Manager"])
		self.assertTrue(_user_has_doc_access("BOM", bom.name, self.manager_user))

	def test_regular_user_denied(self):
		bom = self._create_confidential_bom(roles=["Confidential Manager"])
		self.assertFalse(_user_has_doc_access("BOM", bom.name, self.regular_user))

	def test_non_confidential_bom_returns_none(self):
		bom = self._create_non_confidential_bom()
		result = has_bom_permission(bom, user=self.regular_user)
		self.assertIsNone(result)

	# -----------------------------------------------------------------------
	# User-level access
	# -----------------------------------------------------------------------

	def test_user_level_access_granted(self):
		bom = self._create_confidential_bom(
			roles=["Confidential Manager"],
			users=[self.regular_user],
		)
		self.assertTrue(_user_has_doc_access("BOM", bom.name, self.regular_user))

	def test_user_level_access_not_granted(self):
		bom = self._create_confidential_bom(roles=["Confidential Manager"])
		self.assertFalse(_user_has_doc_access("BOM", bom.name, self.regular_user))

	# -----------------------------------------------------------------------
	# Time-bound access
	# -----------------------------------------------------------------------

	def test_time_bound_access_active(self):
		from frappe.utils import add_days, today
		bom = self._create_confidential_bom(roles=["Confidential Manager"])
		bom.append("allowed_users", {
			"user": self.regular_user,
			"valid_from": add_days(today(), -1),
			"valid_until": add_days(today(), 1),
		})
		bom.flags.ignore_permissions = True
		bom.save()
		frappe.db.commit()

		self.assertTrue(_user_has_doc_access("BOM", bom.name, self.regular_user))

	def test_time_bound_access_expired(self):
		from frappe.utils import add_days, today
		bom = self._create_confidential_bom(roles=["Confidential Manager"])
		bom.append("allowed_users", {
			"user": self.regular_user,
			"valid_from": add_days(today(), -10),
			"valid_until": add_days(today(), -1),
		})
		bom.flags.ignore_permissions = True
		bom.save()
		frappe.db.commit()

		self.assertFalse(_user_has_doc_access("BOM", bom.name, self.regular_user))

	def test_time_bound_access_not_yet_started(self):
		from frappe.utils import add_days, today
		bom = self._create_confidential_bom(roles=["Confidential Manager"])
		bom.append("allowed_users", {
			"user": self.regular_user,
			"valid_from": add_days(today(), 5),
			"valid_until": add_days(today(), 10),
		})
		bom.flags.ignore_permissions = True
		bom.save()
		frappe.db.commit()

		self.assertFalse(_user_has_doc_access("BOM", bom.name, self.regular_user))

	# -----------------------------------------------------------------------
	# Sub-assembly cascade
	# -----------------------------------------------------------------------

	def test_sub_bom_cascade_allowed(self):
		"""User has access to all sub-BOMs in the tree."""
		sub_bom = self._create_confidential_bom(
			item="CONF_TEST_ITEM_B", sub_item="CONF_TEST_ITEM_C",
			roles=["Confidential Manager"],
		)

		parent_bom = frappe.get_doc({
			"doctype": "BOM",
			"item": "CONF_TEST_ITEM_A",
			"quantity": 1,
			"is_active": 1,
			"is_confidential": 1,
			"items": [{
				"item_code": "CONF_TEST_ITEM_B",
				"qty": 1,
				"uom": "Nos",
				"rate": 100,
				"bom_no": sub_bom.name,
			}],
		})
		parent_bom.append("allowed_roles", {"role": "Confidential Manager"})
		parent_bom.insert(ignore_permissions=True)
		frappe.db.commit()

		result = _check_sub_bom_confidentiality(parent_bom.name, self.manager_user)
		self.assertTrue(result)

	def test_sub_bom_cascade_denied(self):
		"""User lacks access to a confidential sub-BOM."""
		sub_bom = self._create_confidential_bom(
			item="CONF_TEST_ITEM_B", sub_item="CONF_TEST_ITEM_C",
			roles=["Confidential Manager"],
		)

		parent_bom = frappe.get_doc({
			"doctype": "BOM",
			"item": "CONF_TEST_ITEM_A",
			"quantity": 1,
			"is_active": 1,
			"is_confidential": 0,
			"items": [{
				"item_code": "CONF_TEST_ITEM_B",
				"qty": 1,
				"uom": "Nos",
				"rate": 100,
				"bom_no": sub_bom.name,
			}],
		})
		parent_bom.insert(ignore_permissions=True)
		frappe.db.commit()

		result = _check_sub_bom_confidentiality(parent_bom.name, self.regular_user)
		self.assertFalse(result)

	# -----------------------------------------------------------------------
	# List-view query conditions
	# -----------------------------------------------------------------------

	def test_query_conditions_admin_sees_all(self):
		conditions = get_bom_permission_query_conditions("Administrator")
		self.assertEqual(conditions, "")

	def test_query_conditions_non_empty_for_regular(self):
		conditions = get_bom_permission_query_conditions(self.regular_user)
		self.assertIn("is_confidential", conditions)
		self.assertIn("Confidential User Mapping", conditions)

	# -----------------------------------------------------------------------
	# Whitelisted check_bom_permission
	# -----------------------------------------------------------------------

	def test_check_bom_permission_api_allowed(self):
		bom = self._create_confidential_bom(roles=["Confidential Manager"])
		frappe.set_user(self.manager_user)
		try:
			result = check_bom_permission(bom.name)
			self.assertTrue(result)
		finally:
			frappe.set_user("Administrator")

	def test_check_bom_permission_api_denied(self):
		bom = self._create_confidential_bom(roles=["Confidential Manager"])
		frappe.set_user(self.regular_user)
		try:
			result = check_bom_permission(bom.name)
			self.assertFalse(result)
		finally:
			frappe.set_user("Administrator")

	# -----------------------------------------------------------------------
	# Audit trail
	# -----------------------------------------------------------------------

	def test_access_log_created_on_view(self):
		bom = self._create_confidential_bom(roles=["Confidential Manager"])
		has_bom_permission(bom, user=self.manager_user)

		logs = frappe.get_all(
			"Confidential Access Log",
			filters={
				"reference_doctype": "BOM",
				"reference_name": bom.name,
				"user": self.manager_user,
				"access_type": "View",
			},
		)
		self.assertGreaterEqual(len(logs), 1)

	def test_access_log_created_on_deny(self):
		bom = self._create_confidential_bom(roles=["Confidential Manager"])
		has_bom_permission(bom, user=self.regular_user)

		logs = frappe.get_all(
			"Confidential Access Log",
			filters={
				"reference_doctype": "BOM",
				"reference_name": bom.name,
				"user": self.regular_user,
				"access_type": "Denied",
			},
		)
		self.assertGreaterEqual(len(logs), 1)

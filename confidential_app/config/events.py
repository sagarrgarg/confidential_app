import frappe
from confidential_app.confidential_app.utils.permissions import clear_permission_cache


def on_app_update():
	"""Clear permission cache when app is updated."""
	clear_permission_cache()


def on_login(login_manager):
	"""Clear permission cache when user logs in."""
	clear_permission_cache()


def after_migrate():
	"""Clear permission cache and sync custom fields after migrations."""
	clear_permission_cache()
	try:
		from confidential_app.confidential_app.install import create_required_custom_fields
		create_required_custom_fields()
	except Exception:
		pass


def after_sync_fixtures():
	"""Clear permission cache after syncing fixtures."""
	clear_permission_cache()

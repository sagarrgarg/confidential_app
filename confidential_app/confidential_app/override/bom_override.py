"""
Server-side BOM access restriction for confidential BOMs.

Patches ERPNext functions that return BOM data without going through
Frappe's standard has_permission hook (i.e. SQL-based reads).

Patched functions:
  - get_bom_items          (whitelisted, also registered via override_whitelisted_methods)
  - get_bom_items_as_dict  (internal, used by Work Order / Stock Entry / Production Plan)
  - make_work_order        (whitelisted, prevents WO creation from inaccessible BOMs)
"""

import frappe
from frappe import _

from confidential_app.confidential_app.utils.permissions import (
    _is_admin,
    _is_protection_enabled,
    _user_has_doc_access,
    debug_log,
    has_bom_permission,
    has_stock_entry_submit_permission,
    has_work_order_permission,
)

_CONFIDENTIAL_HOOKS = {
    "BOM": has_bom_permission,
    "Stock Entry": has_stock_entry_submit_permission,
    "Work Order": has_work_order_permission,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _assert_bom_access(bom_name, action_label="access"):
    """Raise PermissionError if the current user may not access *bom_name*.

    Skipped when the confidential system is disabled, no BOM is specified,
    or the caller is an admin / the BOM is not confidential.
    """
    if not _is_protection_enabled() or not bom_name:
        return

    user = frappe.session.user
    if _is_admin(user):
        return

    is_confidential = frappe.db.get_value("BOM", bom_name, "is_confidential")
    if not is_confidential:
        return

    if not _user_has_doc_access("BOM", bom_name, user):
        debug_log(
            f"BLOCKED: {user} tried to {action_label} "
            f"confidential BOM {bom_name}"
        )
        frappe.throw(
            _("You don't have permission to {0} confidential BOM {1}.").format(
                action_label, bom_name
            ),
            frappe.PermissionError,
        )


# ---------------------------------------------------------------------------
# Originals (captured at import time for delegation)
# ---------------------------------------------------------------------------

from erpnext.manufacturing.doctype.bom.bom import (
    get_bom_items as _original_get_bom_items,
    get_bom_items_as_dict as _original_get_bom_items_as_dict,
)
from erpnext.manufacturing.doctype.work_order.work_order import (
    make_work_order as _original_make_work_order,
)


# ---------------------------------------------------------------------------
# Wrappers
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_bom_items_with_permission_check(bom, company, qty=1, fetch_exploded=1):
    """Drop-in replacement for erpnext…bom.get_bom_items with access guard."""
    _assert_bom_access(bom, "access items of")
    return _original_get_bom_items(
        bom=bom, company=company, qty=float(qty), fetch_exploded=int(fetch_exploded)
    )


def get_bom_items_as_dict_with_permission_check(
    bom,
    company,
    qty=1,
    fetch_exploded=1,
    fetch_scrap_items=0,
    include_non_stock_items=False,
    fetch_qty_in_stock_uom=True,
):
    """Drop-in replacement for erpnext…bom.get_bom_items_as_dict with access guard.

    This is the core SQL function used by Work Order, Stock Entry, and
    Production Plan to explode a BOM into raw material rows. Without this
    patch, any code path that calls get_bom_items_as_dict (including the
    POW dashboard service layer) would bypass has_permission entirely.
    """
    _assert_bom_access(bom, "read materials of")
    return _original_get_bom_items_as_dict(
        bom=bom,
        company=company,
        qty=qty,
        fetch_exploded=fetch_exploded,
        fetch_scrap_items=fetch_scrap_items,
        include_non_stock_items=include_non_stock_items,
        fetch_qty_in_stock_uom=fetch_qty_in_stock_uom,
    )


@frappe.whitelist()
def make_work_order_with_permission_check(
    bom_no, item, qty=0, project=None, variant_items=None, use_multi_level_bom=None
):
    """Drop-in replacement for erpnext…work_order.make_work_order with BOM guard."""
    _assert_bom_access(bom_no, "create a Work Order from")
    return _original_make_work_order(
        bom_no=bom_no,
        item=item,
        qty=qty,
        project=project,
        variant_items=variant_items,
        use_multi_level_bom=use_multi_level_bom,
    )


# ---------------------------------------------------------------------------
# Guard: inject confidential conditions into DatabaseQuery even when
# ignore_permissions=True (i.e. frappe.get_all)
# ---------------------------------------------------------------------------

from confidential_app.config.settings import MANAGED_DOCTYPES

_original_build_conditions = None


def _patched_build_conditions(self):
    """Wraps DatabaseQuery.build_conditions to always inject confidential
    SQL conditions for BOM / Stock Entry / Work Order, even when
    ``ignore_permissions=True`` (which is set by ``frappe.get_all``).
    """
    _original_build_conditions(self)

    if (
        self.doctype in MANAGED_DOCTYPES
        and self.flags.ignore_permissions
        and _is_protection_enabled()
    ):
        user = self.user or frappe.session.user
        if not _is_admin(user):
            from confidential_app.confidential_app.utils.permissions import (
                get_permission_query_conditions,
            )
            condition = get_permission_query_conditions(self.doctype, user)
            if condition:
                self.conditions.append(f"({condition})")


# ---------------------------------------------------------------------------
# Guard: enforce has_permission on frappe.get_doc for confidential DocTypes
# ---------------------------------------------------------------------------

_original_get_doc = None


def _check_confidential_doc_access(doc):
    """Run the confidential has_permission hook for *doc*.

    Returns silently when access is allowed.  Raises
    ``frappe.PermissionError`` when the current user may not view the
    document.

    Skipped when:
    - doc is None or has no name (unsaved new docs)
    - the doctype is not in MANAGED_DOCTYPES
    - ``frappe.flags.ignore_permissions`` or the re-entry guard is set
    - the confidential system is globally disabled
    - the user is an admin
    - the document is not confidential
    """
    if (
        not doc
        or getattr(doc, "doctype", None) not in MANAGED_DOCTYPES
        or not getattr(doc, "name", None)
        or getattr(frappe.flags, "ignore_permissions", False)
        or getattr(frappe.flags, "_conf_get_doc_guard", False)
        or not _is_protection_enabled()
    ):
        return

    user = frappe.session.user
    if _is_admin(user):
        return

    is_confidential = getattr(doc, "is_confidential", 0)
    if not is_confidential:
        return

    hook_fn = _CONFIDENTIAL_HOOKS.get(doc.doctype)
    if not hook_fn:
        return

    frappe.flags._conf_get_doc_guard = True
    try:
        result = hook_fn(doc, user=user, ptype="read")
    finally:
        frappe.flags._conf_get_doc_guard = False

    if result is False:
        frappe.throw(
            _("You don't have permission to access this confidential {0}.").format(
                _(doc.doctype)
            ),
            frappe.PermissionError,
        )


def _patched_get_doc(*args, **kwargs):
    """Wraps ``frappe.get_doc`` to run the confidential has_permission
    hook for BOM / Stock Entry / Work Order after loading.

    ``frappe.get_doc`` from Python does *not* trigger ``has_permission``
    hooks by default — those only fire through the web API layer.  This
    patch closes that gap.

    Uses ``_check_confidential_doc_access`` which calls the **same**
    hook function the web API would call (e.g.
    ``has_stock_entry_submit_permission`` for Stock Entry, which includes
    BOM-cascade logic).

    A re-entry guard (``frappe.flags._conf_get_doc_guard``) prevents
    infinite recursion when hook callbacks themselves call
    ``frappe.get_doc``.
    """
    doc = _original_get_doc(*args, **kwargs)
    _check_confidential_doc_access(doc)
    return doc


# ---------------------------------------------------------------------------
# Guard: enforce has_permission on frappe.get_cached_doc (cache-hit path)
# ---------------------------------------------------------------------------

def _make_patched_get_cached_doc(original_fn):
    """Factory that returns a patched ``get_cached_doc`` wrapper.

    ``frappe.get_cached_doc`` returns documents from Redis cache without
    calling ``frappe.get_doc`` on cache hits. This wrapper ensures the
    confidential access check still runs for cached documents.
    """
    def _patched_get_cached_doc(*args, **kwargs):
        doc = original_fn(*args, **kwargs)
        _check_confidential_doc_access(doc)
        return doc
    return _patched_get_cached_doc


# ---------------------------------------------------------------------------
# Patch application (called from hooks: before_request, boot_session, after_app_install)
# ---------------------------------------------------------------------------

_patches_applied = False


def apply_patches(app_name=None):
    """Monkey-patch ERPNext modules and Frappe core at runtime.

    override_whitelisted_methods in hooks.py handles the two @whitelist
    endpoints (get_bom_items, make_work_order) for frappe.call routing.
    This function patches at the module level so that direct Python imports
    of these functions also go through the permission check.

    Additionally patches:
    - ``DatabaseQuery.build_conditions`` so ``frappe.get_all`` cannot
      bypass confidential query filters.
    - ``frappe.get_doc`` so loading a confidential document from Python
      triggers the same access check as the web API.

    Safe to call multiple times (idempotent via _patches_applied flag).
    """
    global _patches_applied, _original_build_conditions, _original_get_doc
    if _patches_applied:
        return
    _patches_applied = True

    import erpnext.manufacturing.doctype.bom.bom as bom_module
    import erpnext.manufacturing.doctype.work_order.work_order as wo_module

    bom_module.get_bom_items = get_bom_items_with_permission_check
    bom_module.get_bom_items_as_dict = get_bom_items_as_dict_with_permission_check
    wo_module.make_work_order = make_work_order_with_permission_check

    from frappe.model.db_query import DatabaseQuery
    _original_build_conditions = DatabaseQuery.build_conditions
    DatabaseQuery.build_conditions = _patched_build_conditions

    _original_get_doc = frappe.get_doc
    frappe.get_doc = _patched_get_doc

    _original_get_cached_doc = frappe.get_cached_doc
    frappe.get_cached_doc = _make_patched_get_cached_doc(_original_get_cached_doc)

    debug_log(
        "Confidential patches applied "
        "(get_bom_items + get_bom_items_as_dict + make_work_order "
        "+ DatabaseQuery.build_conditions + frappe.get_doc + frappe.get_cached_doc)"
    )

"""
Document event handlers (validate, before_insert, on_update_after_submit)
for the Confidential App.

Registered in hooks.py under doc_events for BOM, Stock Entry, Work Order.
"""

import frappe
from frappe import _

from .permissions import (
    _is_admin,
    _is_protection_enabled,
    _user_has_doc_access,
    check_bom_permission,
    clear_permission_cache,
    invalidate_bom_cache,
    debug_log,
)
from confidential_app.config.settings import ADMIN_ROLES


CONFIDENTIALITY_ADMIN_ROLES = set(ADMIN_ROLES) | {"Confidential Manager"}


def _user_can_change_confidentiality():
    """Return True if the current user may toggle is_confidential / allowed_roles / allowed_users."""
    return bool(CONFIDENTIALITY_ADMIN_ROLES & set(frappe.get_roles()))


def _assert_linked_bom_access(bom_no, parent_doctype):
    """Block the operation if the linked BOM is confidential and the user lacks access."""
    if not _is_protection_enabled() or not bom_no:
        return

    if _is_admin(frappe.session.user):
        return

    if not check_bom_permission(bom_no):
        frappe.throw(
            _("You don't have permission to use confidential BOM {0} in this {1}.").format(
                bom_no, parent_doctype
            ),
            frappe.PermissionError,
        )


# ---------------------------------------------------------------------------
# BOM events
# ---------------------------------------------------------------------------

def validate_bom_permissions_on_save(doc, method=None):
    """BOM validate hook – enforce who may change confidentiality settings."""
    if not _is_protection_enabled():
        return

    if _is_admin(frappe.session.user):
        _check_confidentiality_change_notifications(doc)
        return

    if _user_can_change_confidentiality():
        if doc.is_confidential and not doc.get("allowed_roles") and not doc.get("allowed_users"):
            frappe.throw(_("You must specify at least one allowed role or user for a confidential BOM."))
        _check_confidentiality_change_notifications(doc)
        return

    if doc.is_confidential and not doc.get("allowed_roles") and not doc.get("allowed_users"):
        frappe.throw(_("You must specify at least one allowed role or user for a confidential BOM."))

    if not doc.is_new():
        _block_confidentiality_modification(doc, "BOM")

    _check_confidentiality_change_notifications(doc)


def update_stock_entries_on_bom_change(doc, method=None):
    """BOM on_update_after_submit hook – propagate confidentiality changes."""
    if not _is_protection_enabled():
        return

    old_doc = doc.get_doc_before_save()
    if not old_doc:
        return

    confidentiality_changed = old_doc.is_confidential != doc.is_confidential

    old_roles = {d.role for d in old_doc.get("allowed_roles", [])}
    new_roles = {d.role for d in doc.get("allowed_roles", [])}
    roles_changed = old_roles != new_roles

    old_users = {(d.user, str(d.valid_from or ""), str(d.valid_until or "")) for d in old_doc.get("allowed_users", [])}
    new_users = {(d.user, str(d.valid_from or ""), str(d.valid_until or "")) for d in doc.get("allowed_users", [])}
    users_changed = old_users != new_users

    if not (confidentiality_changed or roles_changed or users_changed):
        return

    # Invalidate stale permission cache for this BOM
    invalidate_bom_cache(doc.name)
    clear_permission_cache()

    debug_log(f"Updating linked documents for BOM {doc.name} due to confidentiality changes")

    _update_linked_documents(doc, "Stock Entry")
    _update_linked_documents(doc, "Work Order")


# ---------------------------------------------------------------------------
# Stock Entry events
# ---------------------------------------------------------------------------

def validate_stock_entry_permissions_on_save(doc, method=None):
    """Stock Entry validate hook."""
    if not _is_protection_enabled():
        return

    _assert_linked_bom_access(doc.bom_no, "Stock Entry")

    if _is_admin(frappe.session.user):
        return

    if _user_can_change_confidentiality():
        if doc.is_confidential and not doc.get("allowed_roles") and not doc.get("allowed_users"):
            frappe.throw(_("You must specify at least one allowed role or user for a confidential Stock Entry."))
        return

    if doc.bom_no and doc.purpose in ("Manufacture", "Material Transfer for Manufacture"):
        if _user_has_doc_access("BOM", doc.bom_no, frappe.session.user):
            return

    if doc.is_confidential and not doc.get("allowed_roles") and not doc.get("allowed_users"):
        frappe.throw(_("You must specify at least one allowed role or user for a confidential Stock Entry."))

    if not doc.is_new():
        _block_confidentiality_modification(doc, "Stock Entry")


def set_stock_entry_confidentiality(doc, method=None):
    """Stock Entry before_insert hook – copy confidentiality from BOM."""
    if not _is_protection_enabled() or not doc.bom_no:
        return

    try:
        bom = frappe.get_doc("BOM", doc.bom_no)
    except frappe.PermissionError:
        is_confidential = frappe.db.get_value("BOM", doc.bom_no, "is_confidential")
        if is_confidential:
            frappe.throw(
                _("You don't have permission to create Stock Entries for this confidential BOM."),
                frappe.PermissionError,
            )
        return
    except frappe.DoesNotExistError:
        return

    if bom.is_confidential:
        doc.is_confidential = 1
        _copy_access_lists(bom, doc)
    else:
        doc.is_confidential = 0
        doc.set("allowed_roles", [])
        doc.set("allowed_users", [])


# ---------------------------------------------------------------------------
# Work Order events
# ---------------------------------------------------------------------------

def validate_work_order_permissions_on_save(doc, method=None):
    """Work Order validate hook."""
    if not _is_protection_enabled():
        return

    _assert_linked_bom_access(doc.bom_no, "Work Order")

    if _is_admin(frappe.session.user):
        return

    if _user_can_change_confidentiality():
        if doc.is_confidential and not doc.get("allowed_roles") and not doc.get("allowed_users"):
            frappe.throw(_("You must specify at least one allowed role or user for a confidential Work Order."))
        return

    if doc.bom_no:
        if _user_has_doc_access("BOM", doc.bom_no, frappe.session.user):
            return

    if doc.is_confidential and not doc.get("allowed_roles") and not doc.get("allowed_users"):
        frappe.throw(_("You must specify at least one allowed role or user for a confidential Work Order."))

    if not doc.is_new():
        _block_confidentiality_modification(doc, "Work Order")


def set_work_order_confidentiality(doc, method=None):
    """Work Order before_insert hook – copy confidentiality from BOM."""
    if not _is_protection_enabled() or not doc.bom_no:
        return

    try:
        bom = frappe.get_doc("BOM", doc.bom_no)
    except frappe.PermissionError:
        is_confidential = frappe.db.get_value("BOM", doc.bom_no, "is_confidential")
        if is_confidential:
            frappe.throw(
                _("You don't have permission to create Work Orders for this confidential BOM."),
                frappe.PermissionError,
            )
        return
    except frappe.DoesNotExistError:
        return

    if bom.is_confidential:
        doc.is_confidential = 1
        _copy_access_lists(bom, doc)
    else:
        doc.is_confidential = 0
        doc.set("allowed_roles", [])
        doc.set("allowed_users", [])


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _block_confidentiality_modification(doc, doctype):
    """Prevent non-admins from changing confidentiality settings on existing docs."""
    old_doc = doc.get_doc_before_save()
    if not old_doc:
        return

    confidentiality_changed = old_doc.is_confidential != doc.is_confidential

    old_roles = {d.role for d in old_doc.get("allowed_roles", [])}
    new_roles = {d.role for d in doc.get("allowed_roles", [])}
    roles_changed = old_roles != new_roles

    old_users = {d.user for d in old_doc.get("allowed_users", [])}
    new_users = {d.user for d in doc.get("allowed_users", [])}
    users_changed = old_users != new_users

    if confidentiality_changed or roles_changed or users_changed:
        frappe.throw(
            _("Only System Manager or Confidential Manager can change the confidentiality "
              "settings of an existing {0}.").format(doctype),
            frappe.PermissionError,
        )


def _copy_access_lists(source_doc, target_doc):
    """Copy allowed_roles and allowed_users from source to target document."""
    target_doc.set("allowed_roles", [])
    for role_row in source_doc.get("allowed_roles", []):
        target_doc.append("allowed_roles", {"role": role_row.role})

    target_doc.set("allowed_users", [])
    for user_row in source_doc.get("allowed_users", []):
        target_doc.append("allowed_users", {
            "user": user_row.user,
            "valid_from": user_row.valid_from,
            "valid_until": user_row.valid_until,
        })


def _check_confidentiality_change_notifications(doc):
    """Send notifications if confidentiality status changed."""
    if doc.is_new():
        if doc.is_confidential:
            _fire_notification(doc, "marked")
        return

    old_doc = doc.get_doc_before_save()
    if not old_doc:
        return

    if old_doc.is_confidential != doc.is_confidential:
        action = "marked" if doc.is_confidential else "unmarked"
        _fire_notification(doc, action)
        return

    if doc.is_confidential:
        old_roles = {d.role for d in old_doc.get("allowed_roles", [])}
        new_roles = {d.role for d in doc.get("allowed_roles", [])}
        if old_roles != new_roles:
            try:
                from confidential_app.confidential_app.utils.notifications import notify_roles_changed
                notify_roles_changed(doc, old_roles, new_roles)
            except Exception:
                pass


def _fire_notification(doc, action):
    try:
        from confidential_app.confidential_app.utils.notifications import notify_confidentiality_change
        notify_confidentiality_change(doc, action)
    except Exception:
        pass


def _update_linked_documents(bom_doc, doctype):
    """Update all linked documents of a given type when BOM confidentiality changes."""
    linked_docs = frappe.get_all(
        doctype,
        filters={"bom_no": bom_doc.name, "docstatus": ["in", [0, 1]]},
        pluck="name",
    )

    for doc_name in linked_docs:
        try:
            linked = frappe.get_doc(doctype, doc_name)
            needs_update = False

            if linked.is_confidential != bom_doc.is_confidential:
                linked.is_confidential = bom_doc.is_confidential
                needs_update = True

            current_roles = {d.role for d in linked.get("allowed_roles", [])}
            new_roles = {d.role for d in bom_doc.get("allowed_roles", [])}
            if current_roles != new_roles:
                linked.set("allowed_roles", [])
                for role_name in new_roles:
                    linked.append("allowed_roles", {"role": role_name})
                needs_update = True

            current_users = {d.user for d in linked.get("allowed_users", [])}
            new_users_data = bom_doc.get("allowed_users", [])
            new_user_names = {d.user for d in new_users_data}
            if current_users != new_user_names:
                linked.set("allowed_users", [])
                for user_row in new_users_data:
                    linked.append("allowed_users", {
                        "user": user_row.user,
                        "valid_from": user_row.valid_from,
                        "valid_until": user_row.valid_until,
                    })
                needs_update = True

            if needs_update:
                linked.flags.ignore_permissions = True
                linked.flags.ignore_validate = True
                linked.flags.ignore_mandatory = True
                linked.save()
                debug_log(f"Updated {doctype} {doc_name} based on BOM {bom_doc.name} change")
        except Exception as e:
            frappe.log_error(
                f"Error propagating confidentiality to {doctype} {doc_name}: {e}",
                "Confidential Propagation Error",
            )

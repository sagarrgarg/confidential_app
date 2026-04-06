# Confidential App – Psychological Handbook

## Architectural Intent

This app exists to gate access to sensitive BOM/manufacturing data without forking or overriding ERPNext core doctypes. It layers on top using Frappe's hook system: `has_permission`, `permission_query_conditions`, `doc_events`, and custom fields.

## Key Design Constraints

1. **Permission checks must evaluate saved (DB) state, not in-memory state.** Frappe calls `has_permission` before committing a save, so the doc object may carry unsaved form values. Always use `frappe.db.get_value` for the `is_confidential` flag inside permission hooks.

2. **Confidential Manager is the operational role; System Manager is the super-admin.** Both should be able to toggle confidentiality. `Confidential User` can view/work with confidential items but not change their classification.

3. **Child table `Confidential Role Mapping` is the source of truth for allowed roles.** It lives as a child of BOM/Stock Entry/Work Order. The permission hook queries it directly via SQL, bypassing ORM caching.

4. **Monkey-patching `get_bom_items`, `get_bom_items_as_dict`, `make_work_order`** is necessary because ERPNext doesn't expose hooks for those functions. They are applied via `before_request` and `boot_session` with an idempotency guard (`_patches_applied`).

5. **Frappe passes `ptype=` not `permission_type=` to has_permission hooks.** Always use `ptype` as the parameter name and accept `**kwargs` as a catch-all.

6. **Custom field fixtures must be consistent across doctypes.** All three doctypes (BOM, Stock Entry, Work Order) must have `permlevel: 2` and `allow_on_submit: 1` for `is_confidential` and `allowed_roles` fields.

7. **Permission cache must be invalidated when confidentiality changes.** The in-process `_permission_cache` can hold stale "allow" results for up to `PERMISSION_CACHE_TIMEOUT` seconds. `invalidate_bom_cache(bom_name)` must be called in `update_stock_entries_on_bom_change`.

8. **Never call `frappe.db.commit()` inside doc events.** It breaks the single-transaction-per-request model and can cause partial state if later operations fail.

9. **Use `frappe.db.escape()` for SQL string interpolation.** Manual quote escaping breaks across database backends (MySQL vs PostgreSQL, ANSI_QUOTES mode).

## Anti-Patterns to Avoid

- Do not read in-memory doc fields inside `has_permission` hooks for values that the user may be changing in the same request.
- Do not silently swallow `frappe.PermissionError` in validate handlers – always re-raise.
- Do not restrict confidentiality management to only `System Manager` – that defeats the purpose of the `Confidential Manager` role.
- Do not assume `has_permission` hooks cover all data access. ERPNext has many internal functions (e.g. `get_bom_items_as_dict`) that use raw SQL and bypass Frappe's permission layer entirely. These must be monkey-patched or overridden separately.
- Do not rely solely on `override_whitelisted_methods` for non-whitelisted internal functions. Those require monkey-patching via `apply_patches` at module level.
- When a new ERPNext whitelisted method is discovered that returns BOM data, it must be added to either `override_whitelisted_methods` or monkey-patched in `apply_patches`. Audit periodically.
- Do not use `after_app_init` as a hook — Frappe does not dispatch it. Use `before_request` with an idempotency guard for runtime patches.
- Do not use `frappe.db.commit()` inside doc_events — it creates partial transaction boundaries.
- Do not use hardcoded file paths for logging — use `frappe.logger("confidential_app")` for portability.
- Do not declare has_permission hook params as `permission_type=` — Frappe passes `ptype=`. Using the wrong name makes the parameter always None.
- Do not use manual SQL string escaping (double-quoting) — use `frappe.db.escape()` for DB-engine portability.
- Do not maintain duplicate source files at shallow vs nested paths — it causes import confusion and stale behavior.
- Do not call `frappe.get_doc("Confidential Settings")` on hot paths — cache the result in-process with a short TTL.

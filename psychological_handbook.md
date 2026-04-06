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

## Deep Defence: `frappe.get_all` and `frappe.get_doc` Are Not Safe by Default

Two critical Frappe internals make confidential data protection fragile:

1. **`frappe.get_all()` sets `ignore_permissions=True` internally.** This completely skips `permission_query_conditions` hooks. Any app — including ERPNext itself — that calls `frappe.get_all("BOM")` will return confidential BOMs to unauthorized users. The confidential app patches `DatabaseQuery.build_conditions` to inject the confidential SQL conditions even when `ignore_permissions=True`.

2. **`frappe.get_doc()` from Python does NOT trigger `has_permission` hooks.** The `has_permission` hook only fires when the document is loaded through the web API layer (desk form load, REST API). Direct Python calls like `frappe.get_doc("BOM", name)` silently return the document regardless of confidentiality. The confidential app patches `frappe.get_doc` to perform the access check after loading.

These patches form a "defence in depth" layer — even if a third-party app uses `frappe.get_all`, `frappe.get_doc`, or `frappe.get_cached_doc` carelessly, confidential documents are still protected.

3. **`frappe.get_cached_doc()` has a cache-hit path that bypasses `get_doc`.** When a document is found in Redis cache, `get_cached_doc` returns it directly without calling `get_doc`. This means our `get_doc` patch alone doesn't cover all read paths. We also patch `get_cached_doc` with the same `_check_confidential_doc_access` check.

**Important: always call the full hook function, not `_user_has_doc_access` directly.** The `_check_confidential_doc_access` helper calls the same hook function that the web API would call (e.g. `has_stock_entry_submit_permission` for Stock Entry). This is critical because some hooks have cascade logic — Stock Entry's hook grants access to users who have BOM-level access, even if they don't have direct SE access. Using `_user_has_doc_access` alone would miss this cascade and incorrectly block authorized users.

**Important re-entry guard:** The `frappe.get_doc` patch uses `frappe.flags._conf_get_doc_guard` to prevent infinite recursion. Any permission-hook callback that itself calls `frappe.get_doc` on a managed DocType must set this flag before the call and clear it afterward (see `has_stock_entry_submit_permission` for the pattern).

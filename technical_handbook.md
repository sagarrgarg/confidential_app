# Confidential App – Technical Handbook

## Architecture Overview

Custom Frappe app that adds confidentiality controls to BOM, Stock Entry, and Work Order doctypes. Uses custom fields (`is_confidential`, `allowed_roles`), `has_permission` hooks, `permission_query_conditions`, and `doc_events` (validate, on_update_after_submit, before_insert) to enforce access.

**Authoritative code path:** `confidential_app/confidential_app/` (nested package). Legacy duplicates exist at `confidential_app/utils/` and `confidential_app/override/` but are **not** wired by hooks.

---

## Change Log

### 2026-04-06 – Fix: Non-system users unable to update BOM to confidential after submit

**What changed:**

1. **`permissions.py` → `has_doctype_permission()`** – Changed `is_confidential` lookup to always read from the database (`frappe.db.get_value`) instead of reading from the in-memory doc object first.

   *Why:* During "update after submit", Frappe calls `has_permission` before the save is committed. The in-memory doc already has `is_confidential = 1` (the new value), but the `allowed_roles` child table rows have not been written to the DB yet. The DB query for allowed roles returned nothing, causing the hook to return `False` and block the save with a permission error.

2. **`validations.py` → `validate_bom_permissions_on_save()`, `validate_stock_entry_permissions_on_save()`, `validate_work_order_permissions_on_save()`** – Expanded the set of roles allowed to change confidentiality settings from only `System Manager` to include `Confidential Manager` (and `Administrator`).

   *Why:* Even after fixing the permission hook, the validate event would still block any non-System-Manager user from toggling `is_confidential` or editing `allowed_roles` on existing documents. `Confidential Manager` is the designated role for managing confidentiality.

**Impacted modules:** BOM, Stock Entry, Work Order – all confidential permission checks and save validations.

**Migration:** None required. Code-only change.

---

### 2026-04-06 – Server-side BOM access restriction for external apps

**Problem:** Third-party apps (e.g. POW dashboard via warehousesuite) could access confidential BOM data because ERPNext's internal functions like `get_bom_items_as_dict` use raw SQL and never call Frappe's `has_permission`. The `has_permission` hook only fires on `frappe.get_doc` calls, leaving SQL-based paths wide open.

**What changed:**

1. **`bom_override.py` (rewritten)** – Added three wrappers:
   - `get_bom_items_with_permission_check` → guards `get_bom_items` (whitelisted)
   - `get_bom_items_as_dict_with_permission_check` → guards `get_bom_items_as_dict` (internal SQL function used by Work Order, Stock Entry, Production Plan)
   - `make_work_order_with_permission_check` → guards `make_work_order` (whitelisted, prevents WO creation from inaccessible BOMs)

   All three delegate to the original ERPNext function after verifying the user has access via `check_bom_permission`.

2. **`hooks.py` → `override_whitelisted_methods`** – Registered overrides for:
   - `erpnext…bom.get_bom_items`
   - `erpnext…work_order.make_work_order`

   This is the Frappe-native way to intercept whitelisted API endpoints (more reliable than monkey-patching alone for `frappe.call` invocations).

3. **`hooks.py` → `apply_patches` (after_app_init)** – Now patches both `get_bom_items` and `get_bom_items_as_dict` at the module level. The latter is not whitelisted and must be replaced via monkey-patch.

4. **`validations.py` → `_assert_linked_bom_access()`** – New helper called at the top of `validate_work_order_permissions_on_save` and `validate_stock_entry_permissions_on_save`. Blocks saving any Work Order or Stock Entry that links to a confidential BOM the user cannot access.

**Coverage map (attack surface closed):**

| Access path | Protection layer |
|---|---|
| `frappe.get_doc("BOM", name)` | `has_permission` hook (existing) |
| `frappe.get_all("BOM", ...)` | `permission_query_conditions` (existing) |
| `frappe.call("get_bom_items", bom=...)` | `override_whitelisted_methods` + monkey-patch |
| `get_bom_items_as_dict(bom, ...)` (internal) | monkey-patch in `apply_patches` |
| `frappe.call("make_work_order", bom_no=...)` | `override_whitelisted_methods` |
| WO/SE validate with confidential BOM | `_assert_linked_bom_access` in doc_events |

**Impacted modules:** bom_override.py, hooks.py, validations.py

**Migration:** None. Run `bench clear-cache` after deploy.

---

### 2026-04-06 – Comprehensive production audit & hardening

Full end-to-end audit of the app, covering security, production stability, cross-app compatibility (warehousesuite/POW dashboard, business_needed_solutions), and fixture correctness.

**Issues found & fixed:**

| Severity | Issue | Fix |
|----------|-------|-----|
| CRITICAL | `ptype` parameter mismatch — Frappe passes `ptype=` but hooks declared `permission_type=`, so the create-permission branch was dead code | Renamed param to `ptype` with `**_kwargs` catch-all in all hook functions |
| CRITICAL | Stale permission cache — `check_bom_permission` cached for 300s, never invalidated when BOM confidentiality changed | Added `invalidate_bom_cache()` + `clear_permission_cache()` calls in `update_stock_entries_on_bom_change` |
| CRITICAL | Work Order custom fields at permlevel 0 (BOM/SE use permlevel 2) and `allow_on_submit: 0` | Fixed fixtures: WO fields now permlevel 2, allow_on_submit 1 |
| HIGH | SQL role escaping used double quotes — breaks on PostgreSQL / ANSI_QUOTES mode | Replaced with `frappe.db.escape()` for all role names and doctype values |
| HIGH | `frappe.db.commit()` inside `update_cancelled_documents_db` doc event — partial transaction risk | Removed; DB changes now commit with the parent request transaction |
| HIGH | `is_enabled()` called `frappe.get_doc()` on every invocation — expensive under load | Added `_is_enabled()` with 30s in-process cache |
| MED | `after_app_init` hook is dead — Frappe never dispatches it | Replaced with `before_request` (idempotent via `_patches_applied` flag) |
| MED | `make_work_order` only in `override_whitelisted_methods`, not monkey-patched — direct Python imports bypass | Added to `apply_patches()` module-level patching |
| MED | `doc is None` in `has_doctype_permission` crashes at `doc.is_new()` | Added None guard with isinstance check before attribute access |
| MED | Duplicate `permissions.py`, `validations.py`, `bom_override.py` at shallow path | Replaced with deprecation stubs that raise ImportError |
| MED | Broad `except Exception` clauses in validations silently swallow errors | Replaced with `doc.get_doc_before_save()` (no extra `get_doc` call / permission check), tightened exception handling |
| MED | `debug_log` used hardcoded file path + `logging.basicConfig` on every call | Replaced with `frappe.logger("confidential_app").debug()` |

**Known remaining issues (warehousesuite / external apps — not in confidential_app scope):**

1. POW dashboard `get_pending_work_orders` uses raw SQL when warehouse filter is set, bypassing `permission_query_conditions` — confidential WOs with `bom_no` can leak in the listing
2. POW dashboard `get_bom_items` in `pow_dashboard.py` catches all exceptions and returns `[]` — masks permission errors as empty results
3. `business_needed_solutions` calls `get_bom_items_as_dict` — works correctly because our monkey-patch is applied, but depends on import ordering

**Migration:** Run `bench clear-cache && bench migrate && bench build --app confidential_app && bench clear-cache` — the `migrate` step is needed to apply the Work Order custom field fixture changes (permlevel + allow_on_submit).

---

### 2026-04-06 – Harden: force confidential filtering on `frappe.get_all` and `frappe.get_doc`

**Problem:** `frappe.get_all` internally sets `ignore_permissions=True`, bypassing `permission_query_conditions`. Additionally, `frappe.get_doc` from Python does not trigger `has_permission` hooks — those only fire through the web API layer. Any third-party app (or ERPNext internal code) calling these functions could leak confidential BOMs, Stock Entries, and Work Orders.

**What changed:**

1. **`bom_override.py` → `_patched_build_conditions()`** — Monkey-patches `DatabaseQuery.build_conditions` to always inject the confidential SQL WHERE clause for BOM / Stock Entry / Work Order, even when `ignore_permissions=True`. This means `frappe.get_all("BOM")` now behaves identically to `frappe.get_list("BOM")` with respect to confidentiality filtering.

2. **`bom_override.py` → `_check_confidential_doc_access(doc)`** — Centralized access check extracted into a shared helper. Calls the **same** hook function registered in `hooks.py` for each DocType (e.g. `has_stock_entry_submit_permission` for Stock Entry, which includes BOM-cascade logic). This ensures Python-level `get_doc` calls enforce identical rules to the web API layer.

3. **`bom_override.py` → `_patched_get_doc()`** — Wraps `frappe.get_doc` to call `_check_confidential_doc_access` after loading. Includes a re-entry guard (`frappe.flags._conf_get_doc_guard`) to prevent infinite recursion when hooks themselves call `frappe.get_doc`.

4. **`bom_override.py` → `_make_patched_get_cached_doc()`** — Wraps `frappe.get_cached_doc` with the same `_check_confidential_doc_access` call. Necessary because `get_cached_doc` has a cache-hit path that bypasses `get_doc` entirely.

5. **`permissions.py` → `has_stock_entry_submit_permission()`** — Sets the `_conf_get_doc_guard` flag before calling `frappe.get_doc("Stock Entry", ...)` to avoid re-entry in the patched `get_doc`.

6. **`apply_patches()`** — Now applies six patches: the three ERPNext function overrides + `DatabaseQuery.build_conditions` + `frappe.get_doc` + `frappe.get_cached_doc`.

**Updated coverage map:**

| Access path | Protection layer |
|---|---|
| `frappe.get_doc("BOM", name)` (web API) | `has_permission` hook |
| `frappe.get_doc("BOM", name)` (Python) | `_patched_get_doc` → `_check_confidential_doc_access` (NEW) |
| `frappe.get_list("BOM", ...)` | `permission_query_conditions` |
| `frappe.get_all("BOM", ...)` | `_patched_build_conditions` (NEW) |
| `frappe.get_cached_doc("BOM", name)` (cache hit) | `_patched_get_cached_doc` → `_check_confidential_doc_access` (NEW) |
| `frappe.get_cached_doc("BOM", name)` (cache miss) | delegates to `frappe.get_doc` → caught |
| `frappe.get_last_doc("BOM")` | `get_all` + `get_doc` → both caught |
| `frappe.call("get_bom_items", bom=...)` | `override_whitelisted_methods` |
| `get_bom_items_as_dict(bom, ...)` (internal) | monkey-patch |
| `frappe.call("make_work_order", bom_no=...)` | `override_whitelisted_methods` |
| WO/SE validate with confidential BOM | `_assert_linked_bom_access` in doc_events |

**Design decisions:**

- `_check_confidential_doc_access` calls the registered hook function (e.g. `has_stock_entry_submit_permission`) instead of raw `_user_has_doc_access`. This ensures the Stock Entry BOM-cascade logic (grant SE access if user has BOM access) works identically whether the doc is loaded via the web API or Python.
- The re-entry guard (`frappe.flags._conf_get_doc_guard`) is request-scoped, set via try/finally, and checked early in the skip list to avoid overhead.
- `frappe.flags.ignore_permissions` is respected as the standard Frappe escape hatch for trusted internal operations.
- `frappe.new_doc()` is unaffected — new docs have `name=None` which triggers an early skip.

**Impacted modules:** `bom_override.py`, `permissions.py`

**Migration:** None. Run `bench clear-cache` after deploy.

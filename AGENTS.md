# Agents

## Cursor Cloud specific instructions

This is a **Frappe/ERPNext custom app** (`confidential_app`) that adds role-based confidentiality controls to manufacturing documents (BOMs, Stock Entries, Work Orders). It runs inside a Frappe Bench environment and requires ERPNext.

### Architecture

- **Frappe Bench** at `/home/ubuntu/frappe-bench` contains the Frappe framework (v15), ERPNext (v15), and this app (symlinked from `/workspace`).
- **Site**: `dev.localhost` (default site), admin password: `admin`.
- **MariaDB** root password: `root`.

### Starting services

```bash
# Start MariaDB and Redis (system services)
sudo service mariadb start
sudo service redis-server start

# Start the full dev server (from bench directory)
cd /home/ubuntu/frappe-bench && bench start
```

`bench start` launches: web server (port 8000), Redis cache (port 13000), Redis queue (port 11000), socketio (port 9000), file watcher, scheduler, and worker.

### Common commands

| Action | Command |
|---|---|
| Dev server | `cd /home/ubuntu/frappe-bench && bench start` |
| Build app assets | `bench build --app confidential_app` |
| Run tests | `bench --site dev.localhost run-tests --app confidential_app` |
| Bench console | `bench --site dev.localhost console` |
| Clear cache | `bench --site dev.localhost clear-cache` |
| Migrate | `bench --site dev.localhost migrate` |

### Gotchas

- The app has **no test files** and **no lint config** of its own. Python files can be checked via `py_compile`. The Frappe test runner works but reports "0 tests ran".
- `bench setup backups` fails because `/usr/bin/crontab` is not available in this environment. This is non-blocking for development.
- After modifying Python files, the `bench start` web process auto-reloads. After modifying JS files, the watcher rebuilds automatically.
- Developer mode is enabled on the site (`developer_mode: 1`). This is required for the app to function correctly in dev.
- ERPNext setup wizard was already run via `erpnext.setup.utils.before_tests` to seed the company, items, etc.

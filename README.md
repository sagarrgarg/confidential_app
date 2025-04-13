# Confidential App for ERPNext

A Frappe application for managing confidential BOMs, Stock Entries, and Work Orders in ERPNext.

## Overview

Confidential App adds role-based permission controls to manufacturing documents in ERPNext. It allows marking certain BOMs, Stock Entries, and Work Orders as confidential, restricting access to users with specific roles.

## Features

- Mark BOMs as confidential and specify which roles can access them
- Automatically propagate confidentiality settings to related Stock Entries and Work Orders
- Control access at the document level with fine-grained permissions
- Efficient permission checks with built-in caching
- Comprehensive logging for troubleshooting

## Installation

### Prerequisites

- Frappe/ERPNext v14 or later
- Python 3.10+

### Steps

1. Install the app:
   ```bash
   bench get-app https://github.com/yourusername/confidential_app
   bench --site yoursite.local install-app confidential_app
   ```

2. Run migrations and restart the server:
   ```bash
   bench --site yoursite.local migrate
   bench restart
   ```

## Configuration

### Environment Variables

- `CONFIDENTIAL_DEBUG`: Set to `1` to enable debug logging (default: `0`)

### Roles

The app creates two roles:
- **Confidential Manager**: Can manage confidential documents and their settings
- **Confidential User**: Can view but not modify confidential documents

## Usage

### Making a BOM Confidential

1. Open or create a BOM
2. Check the "Is Confidential" checkbox
3. Add the roles allowed to access this BOM
4. Save the BOM

### Access Control

- Users with one of the allowed roles can access the confidential document
- System Managers can always access all documents
- Stock Entries and Work Orders created from confidential BOMs automatically inherit the same confidentiality settings

## Troubleshooting

### Debug Logs

Check the debug logs at `/home/ubuntu/frappe-bench/logs/conf_perm_debug.log` when debug mode is enabled.

### Permission Issues

If users cannot access documents they should have access to:
1. Clear the cache: `bench clear-cache`
2. Verify the roles assigned to the user
3. Check that the confidential document has the correct roles specified

## License

This project is licensed under the MIT License - see the LICENSE.txt file for details.

## Support

For support, please open an issue on the GitHub repository or contact the maintainer.

## Development

### Setup for Development

1. Clone the repository
2. Install the app in development mode:
   ```bash
   bench get-app confidential_app /path/to/local/repo
   ```

3. Make changes and test
4. Clear cache after changes: `bench clear-cache`
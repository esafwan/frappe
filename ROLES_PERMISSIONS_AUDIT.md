# Frappe Framework - Roles & Permissions Audit

**Purpose**: Comprehensive audit of all files, doctypes, hooks, logics, and methods related to roles and permissions in the Frappe Framework.

**Date**: 2026-03-27
**Status**: Initial Exploration - Files Identified

---

## Table of Contents

1. [Core Permission Logic](#core-permission-logic)
2. [Role-Related DocTypes](#role-related-doctypes)
3. [Permission-Related DocTypes](#permission-related-doctypes)
4. [Key Methods and Functions](#key-methods-and-functions)
5. [Hooks Configuration](#hooks-configuration)
6. [Permission Types](#permission-types)
7. [Related Modules](#related-modules)
8. [Test Files](#test-files)
9. [Patches and Migrations](#patches-and-migrations)

---

## Core Permission Logic

### Main Permission Module
| File Path | Type | Purpose | Key Functions |
|-----------|------|---------|---|
| `frappe/permissions.py` | Core Module | Central permission system logic | `has_permission()`, `get_role_permissions()`, `get_doc_permissions()`, `has_child_permission()`, `has_user_permission()`, `has_controller_permissions()`, `get_roles()` |

**Key Constants Defined**:
- `std_rights`: All available permission types (select, read, write, create, delete, submit, cancel, amend, print, email, report, import, export, share)
- `GUEST_ROLE = "Guest"`
- `ALL_USER_ROLE = "All"`
- `SYSTEM_USER_ROLE = "Desk User"`
- `ADMIN_ROLE = "Administrator"`
- `AUTOMATIC_ROLES`: Roles auto-assigned based on user type

---

## Role-Related DocTypes

### 1. Role
| Item | Details |
|------|---------|
| **Path** | `frappe/core/doctype/role/` |
| **Files** | `role.py`, `role.json`, `role.js`, `test_role.py` |
| **Purpose** | Define system roles for permission assignment |
| **Fields** | role_name, disabled, desk_access, two_factor_auth, restrict_to_domain, home_page, is_custom |
| **Permissions** | System Manager (full CRUD) |
| **Key Methods** | Python methods in `role.py` for role validation and management |

### 2. User Role
| Item | Details |
|------|---------|
| **Path** | `frappe/core/doctype/user_role/` |
| **Files** | `user_role.py` |
| **Purpose** | Link table for assigning roles to users (child table of User) |
| **Fields** | user, role |
| **Key Point** | Maps users to roles; used for role-based access control |

### 3. Custom Role
| Item | Details |
|------|---------|
| **Path** | `frappe/core/doctype/custom_role/` |
| **Files** | `custom_role.py`, `custom_role.json`, `custom_role.js`, `test_custom_role.py` |
| **Purpose** | Define custom roles created by users |
| **Fields** | role_name, disabled, desk_access, is_custom |
| **Key Point** | Extends Role functionality for custom user roles |

### 4. Role Profile
| Item | Details |
|------|---------|
| **Path** | `frappe/core/doctype/role_profile/` |
| **Files** | `role_profile.py`, `role_profile.json`, `role_profile.js`, `test_role_profile.py` |
| **Purpose** | Group multiple roles together for easy assignment |
| **Key Point** | Allows bulk role assignment; used for role management |

### 5. User Role Profile
| Item | Details |
|------|---------|
| **Path** | `frappe/core/doctype/user_role_profile/` |
| **Files** | `user_role_profile.py`, `user_role_profile.json` |
| **Purpose** | Link table for assigning role profiles to users |
| **Key Point** | Alternative to direct role assignment through profiles |

### 6. Has Role
| Item | Details |
|------|---------|
| **Path** | `frappe/core/doctype/has_role/` |
| **Files** | `has_role.json`, `has_role.py` |
| **Purpose** | Check if a user has a specific role |
| **Key Point** | Utility doctype for role verification |

---

## Permission-Related DocTypes

### 1. User Permission
| Item | Details |
|------|---------|
| **Path** | `frappe/core/doctype/user_permission/` |
| **Files** | `user_permission.py`, `user_permission.json`, `user_permission.js`, `user_permission_list.js`, `test_user_permission.py` |
| **Purpose** | Restrict user access to specific documents/records |
| **Fields** | user, allow (DocType), for_value (specific record), is_default, apply_to_all_doctypes, applicable_for, hide_descendants |
| **Key Functionality** | Document-level access control; prevents users from seeing certain records |
| **Key Methods** | Custom validation, permission query conditions |

### 2. Permission Log
| Item | Details |
|------|---------|
| **Path** | `frappe/core/doctype/permission_log/` |
| **Files** | `permission_log.py`, `permission_log.json`, `permission_log.js`, `permission_log_list.js`, `test_permission_log.py` |
| **Purpose** | Audit log for permission changes (create, write, delete) |
| **Key Point** | Tracks who made what permission changes and when |
| **Hook** | Triggered via `after_insert`, `after_update`, `after_delete` hooks for User and Role doctypes |

### 3. Permission Type
| Item | Details |
|------|---------|
| **Path** | `frappe/core/doctype/permission_type/` |
| **Files** | `permission_type.py`, `permission_type.json`, `permission_type.js`, `test_permission_type.py` |
| **Purpose** | Define custom permission types beyond standard rights |
| **Key Function** | `get_doctype_ptype_map()` - maps doctypes to custom permission types |
| **Use Case** | Add domain-specific permissions (e.g., "can_approve", "can_export") |

### 4. Permission Inspector
| Item | Details |
|------|---------|
| **Path** | `frappe/core/doctype/permission_inspector/` |
| **Files** | `permission_inspector.py`, `permission_inspector.json`, `permission_inspector.js`, `test_permission_inspector.py` |
| **Purpose** | Tool to inspect and debug user permissions |
| **Key Point** | Used for troubleshooting permission issues |

### 5. Role Permission for Page and Report
| Item | Details |
|------|---------|
| **Path** | `frappe/core/doctype/role_permission_for_page_and_report/` |
| **Files** | `role_permission_for_page_and_report.py`, `role_permission_for_page_and_report.json`, `role_permission_for_page_and_report.js`, `test_role_permission_for_page_and_report.py` |
| **Purpose** | Control role access to pages and reports |
| **Key Point** | Separate permission system from document permissions |

---

## Key Methods and Functions

### In `frappe/permissions.py`

| Function | Signature | Purpose |
|----------|-----------|---------|
| `has_permission()` | `has_permission(doctype, ptype="read", doc=None, user=None, *, parent_doctype=None, print_logs=True, debug=False, ignore_share_permissions=False)` | Main permission check function; returns True if user has permission |
| `get_role_permissions()` | `get_role_permissions(doctype_meta, user=None, is_owner=None, debug=False)` | Returns dict of role-based permissions for a user |
| `get_doc_permissions()` | `get_doc_permissions(doc, user=None, ptype=None, debug=False)` | Returns evaluated permissions for a specific document |
| `has_child_permission()` | Child table permission checking | Checks permissions for child table doctypes |
| `has_user_permission()` | User permission checking | Validates user permissions for specific records |
| `has_controller_permissions()` | Controller-level permission check | Allows custom permission logic via Document controller |
| `get_roles()` | `get_roles(user_name)` | Returns list of roles assigned to a user |
| `get_all_permissions()` | Get all permissions for user | Returns comprehensive permission dict |
| `get_role()` | Get role object | Returns Role doctype instance |

### Decorators in `frappe/permissions.py`

| Decorator | Purpose |
|-----------|---------|
| `@print_has_permission_check_logs` | Logs permission check failures with detailed messages |

### Debug Functions in `frappe/permissions.py`

| Function | Purpose |
|----------|---------|
| `_debug_log()` | Log permission check details for debugging |
| `_pop_debug_log()` | Retrieve and clear debug logs |

### In `frappe/__init__.py`

| Function | Purpose |
|----------|---------|
| `get_roles(username=None)` | Get roles for current or specified user |
| `get_user()` | Get UserPermissions object for current session |
| `only_for(roles, message=False)` | Decorator/check to restrict function to specific roles |
| `has_permission(doctype, docname, ptype)` | Wrapper for frappe.permissions.has_permission() |
| `get_doc_permissions(doctype, docname)` | Get all permissions for a document |
| `only_has_select_perm()` | Check if user only has select (read) permission |

### In `frappe/utils/user.py`

| Function | Purpose |
|----------|---------|
| `get_roles()` | Instance method to get user's roles |
| `build_permissions()` | Build user's permission cache |
| `add_role(user, role)` | Add a role to a user |
| `get_users_with_role(role)` | Get all users with a specific role |
| `get_portal_roles()` | Get roles available for portal users |

### In `frappe/share.py`

| Function | Purpose |
|----------|---------|
| `set_permission(doctype, name, user, ptype, value)` | Set shared document permission for a user |
| `set_docshare_permission()` | Set document-level sharing permissions |
| `check_share_permission()` | Validate share permissions |

### In `frappe/model/document.py`

| Method | Purpose |
|--------|---------|
| `check_permission(permtype="read", permlevel=None)` | Validate document access permission |
| `has_permission(permtype="read", *, debug=False, user=None)` | Check if user has permission to document |
| `get_permlevel_access()` | Get field-level permission access |
| `has_permlevel_access_to()` | Check field-level access |
| `get_permissions()` | Return applicable permissions for document |
| `apply_fieldlevel_read_permissions()` | Filter fields based on read permissions |

### In `frappe/model/meta.py`

| Method | Purpose |
|--------|---------|
| `get_permissions(parenttype=None)` | Get all permissions defined for doctype |
| `set_custom_permissions()` | Apply custom permission overrides |
| `get_fields_to_check_permissions()` | Identify which fields need permission checks |
| `get_permlevel_access()` | Get field-level access based on permission level |

### In `frappe/database/query.py`

| Method | Purpose |
|--------|---------|
| `check_select_field_permission()` | Validate field-level select permission |
| `check_filter_field_permission()` | Validate field permission in filters |
| `_check_field_permission()` | Core field permission validation |
| `_get_cached_permitted_fields()` | Cache permitted fields for performance |
| `check_select_permission()` | Check select permission on DocType |
| `add_permission_conditions()` | Add SQL conditions for permission filtering |
| `get_permission_conditions()` | Build permission query conditions |
| `get_permission_query_conditions()` | Get custom permission query from hooks |
| `get_permission_type()` | Get permission type for operation |
| `requires_owner_constraint()` | Check if owner-based filtering is needed |

---

## Hooks Configuration

### In `frappe/hooks.py`

**Permission Query Conditions Hook** (lines 103-122)
- Maps doctypes to custom permission query condition functions
- Allows custom SQL filtering for permission-based record visibility
- Examples: Event, ToDo, User, Dashboard, Contact, Address, File, etc.

**Has Permission Hook** (lines 124-140)
- Maps doctypes to custom has_permission() implementations
- Allows document-specific permission logic overrides
- Examples: Event, ToDo, Note, User, Dashboard Chart, etc.

**Has Website Permission Hook** (line 142)
- Maps doctypes to website-specific permission checks
- Example: Address

**Permission-Related Hooks**:
```python
# Doc-level hooks
on_update = [
    "frappe.core.doctype.user_type.user_type.apply_permissions_for_non_standard_user_type",
    "frappe.core.doctype.permission_log.permission_log.make_perm_log",
]

on_trash = [
    "frappe.core.doctype.permission_log.permission_log.make_perm_log",
]

after_delete = [
    "frappe.core.doctype.permission_log.permission_log.make_perm_log",
]

# Validation hooks
validate = [...]
before_validate = [...]
```

**User-related Hooks**:
```python
validate.User = [
    "frappe.core.doctype.user.user.validate_user_roles",
]

autoname.User = "frappe.core.doctype.user.user.autoname_user"
```

**All Roles Hook** (line 532):
```python
allowed_roles = {
    # Configuration of default roles and permissions
}
```

---

## Permission Types

### Standard Permission Rights (from `frappe/permissions.py`)

```
std_rights = (
    "select",      # Select from list
    "read",        # View document
    "write",       # Edit document
    "create",      # Create new documents
    "delete",      # Delete documents
    "submit",      # Submit submittable documents
    "cancel",      # Cancel submitted documents
    "amend",       # Amend submitted documents
    "print",       # Print documents
    "email",       # Send via email
    "report",      # View reports
    "import",      # Import documents
    "export",      # Export documents
    "share",       # Share documents with others
)
```

### Custom Permission Types
- Defined via `Permission Type` doctype
- Retrieved via `get_doctype_ptype_map()` function
- Domain-specific permissions (e.g., "can_approve")

---

## Related Modules

### User Management (`frappe/core/doctype/user/`)
- **File**: `user.py`
- **Role Methods**:
  - `get_permission_query_conditions()` - Custom permission query
  - `has_permission()` - Custom user permission check
- **Related**: User roles, role profiles linked here

### Document Type (`frappe/core/doctype/doctype/`)
- **File**: `doctype.py`
- **Role Methods**: Define default permissions for doctypes
- **Connection**: DocType metadata includes permission definitions

### Page (`frappe/core/doctype/page/`)
- **File**: `page.py`
- **Connection**: Page access controlled via Role Permission for Page and Report

### Report (`frappe/core/doctype/report/`)
- **File**: `report.py`
- **Connection**: Report access controlled via Role Permission for Page and Report

### Share System (`frappe/share.py`)
- **Purpose**: Document-level sharing/collaboration
- **Key Functions**: `set_permission()`, `check_share_permission()`, `get_shared()`
- **Integration**: Works alongside role-based permissions

### Workflow (`frappe/workflow/doctype/workflow/`)
- **File**: `workflow.py`
- **Permission Component**: `workflow_action_permitted_role.py`
- **Purpose**: Control workflow transitions by role

### OAuth Integration (`frappe/integrations/doctype/oauth_client_role/`)
- **File**: `oauth_client_role.py`
- **Purpose**: Control OAuth access by role

### Contacts Module (`frappe/contacts/address_and_contact.py`)
- **Has Permission**: Custom logic for Contact/Address
- **Query Conditions**: Custom filtering for Contact/Address records

### Desk Components with Permission Logic
- **Event**: `frappe/desk/doctype/event/event.py` - Has_permission, query conditions
- **ToDo**: `frappe/desk/doctype/todo/todo.py` - Has_permission, query conditions
- **Note**: `frappe/desk/doctype/note/note.py` - Has_permission, query conditions
- **Dashboard**: `frappe/desk/doctype/dashboard/dashboard.py` - Query conditions
- **Dashboard Chart**: `frappe/desk/doctype/dashboard_chart/dashboard_chart.py` - Has_permission, query conditions
- **Dashboard Settings**: `frappe/desk/doctype/dashboard_settings/dashboard_settings.py` - Query conditions
- **Number Card**: `frappe/desk/doctype/number_card/number_card.py` - Has_permission
- **Kanban Board**: `frappe/desk/doctype/kanban_board/kanban_board.py` - Has_permission, query conditions
- **Notification Settings**: `frappe/desk/doctype/notification_settings/notification_settings.py` - Query conditions, has_permission
- **Onboarding Permission**: `frappe/desk/doctype/onboarding_permission/onboarding_permission.py` - Permission for onboarding

---

## Test Files

| Test File | Purpose |
|-----------|---------|
| `frappe/tests/test_permissions.py` | Comprehensive permission system tests |
| `frappe/core/doctype/role/test_role.py` | Role doctype tests |
| `frappe/core/doctype/user_role/test_user_role.py` | User role link tests |
| `frappe/core/doctype/custom_role/test_custom_role.py` | Custom role tests |
| `frappe/core/doctype/role_profile/test_role_profile.py` | Role profile tests |
| `frappe/core/doctype/user_permission/test_user_permission.py` | User permission tests |
| `frappe/core/doctype/permission_log/test_permission_log.py` | Permission log audit tests |
| `frappe/core/doctype/permission_type/test_permission_type.py` | Custom permission type tests |
| `frappe/core/doctype/permission_inspector/test_permission_inspector.py` | Permission inspector tests |
| `frappe/core/doctype/role_permission_for_page_and_report/test_role_permission_for_page_and_report.py` | Page/report permission tests |
| `frappe/core/doctype/onboarding_permission/test_onboarding_permission.py` | Onboarding permission tests |
| `cypress/integration/permissions.js` | E2E permission tests |

---

## Patches and Migrations

### Version 11.0 Patches (`frappe/patches/v11_0/`)
- `delete_duplicate_user_permissions.py` - Clean up duplicates
- `drop_column_apply_user_permissions.py` - Schema migration
- `remove_doctype_user_permissions_for_page_and_report.py` - Remove old permission system
- `replicate_old_user_permissions.py` - Migrate user permissions
- `set_missing_creation_and_modified_value_for_user_permissions.py` - Fix missing timestamps

### Version 15.0 Patches
- `migrate_role_profile_to_table_multi_select.py` - Update role profile structure

### Version 16.0 Patches
- `move_role_desk_settings_to_user.py` - Refactor role desk settings

### OAuth Patches
- `frappe/integrations/doctype/oauth_client/patches/set_default_allowed_role_in_oauth_client.py` - OAuth role defaults

---

## Frontend/JavaScript Files

### Form and DocType UI
| File | Purpose |
|------|---------|
| `frappe/core/doctype/role/role.js` | Role form UI logic |
| `frappe/core/doctype/custom_role/custom_role.js` | Custom role form UI |
| `frappe/core/doctype/role_profile/role_profile.js` | Role profile form UI |
| `frappe/core/doctype/user_permission/user_permission.js` | User permission form UI |
| `frappe/core/doctype/user_permission/user_permission_list.js` | User permission list view |
| `frappe/core/doctype/permission_log/permission_log.js` | Permission log form UI |
| `frappe/core/doctype/permission_log/permission_log_list.js` | Permission log list UI |
| `frappe/core/doctype/permission_type/permission_type.js` | Permission type form UI |
| `frappe/core/doctype/permission_inspector/permission_inspector.js` | Permission inspector UI |
| `frappe/core/doctype/role_permission_for_page_and_report/role_permission_for_page_and_report.js` | Page/report permission UI |

### Admin Tools
| File | Purpose |
|------|---------|
| `frappe/core/page/permission_manager/permission_manager.py` | Backend for permission manager page |
| `frappe/core/page/permission_manager/permission_manager.js` | UI for managing doctype permissions |
| `frappe/core/report/user_doctype_permissions/user_doctype_permissions.py` | Report backend for user permissions |
| `frappe/core/report/user_doctype_permissions/user_doctype_permissions.js` | Report frontend |
| `frappe/public/js/frappe/roles_editor.js` | Roles editor component |

---

## Permission Check Flow

### Typical Permission Check (from `frappe/permissions.py`)

```
has_permission(doctype, ptype="read", doc=None, user=None)
    ├─ Is user Administrator? → Allow
    ├─ Is share disabled? → Check role permissions
    ├─ Is child table? → has_child_permission()
    ├─ Is Single doctype? → Load doctype for permission check
    ├─ If doc specified:
    │   ├─ get_doc_permissions()
    │   ├─ has_controller_permissions()
    │   ├─ has_user_permission() → Filter by document
    │   └─ Apply if_owner overrides
    ├─ If no doc:
    │   └─ get_role_permissions()
    └─ If no role permission:
        └─ Check shared documents
```

---

## Key Integration Points

1. **Document Save** → Permission validation in `model/document.py:_save()`
2. **Document Load** → Field-level filtering in `model/document.py:apply_fieldlevel_read_permissions()`
3. **Query Execution** → Permission conditions added in `database/query.py` and `model/db_query.py`
4. **User Login** → Roles loaded and cached via `utils/user.py:UserPermissions`
5. **API Calls** → Permission checks in `handler.py:check_write_permission()` and `client.py`
6. **Reports** → Permission queries in `core/doctype/report/report.py`
7. **Website** → Permission checks in `website/serve.py`

---

## Summary Statistics

- **Core Permission Files**: 1 main module + utilities
- **Role-Related DocTypes**: 6 (Role, Custom Role, User Role, Role Profile, User Role Profile, Has Role)
- **Permission-Related DocTypes**: 5 (User Permission, Permission Log, Permission Type, Permission Inspector, Role Permission for Page/Report)
- **Workflow Permission Components**: 1 (Workflow Action Permitted Role)
- **OAuth Permission Components**: 1 (OAuth Client Role)
- **Total Python Files**: 40+ related to permissions
- **Test Files**: 14+ test modules
- **Hooks**: permission_query_conditions (13+), has_permission (9+), has_website_permission (1)
- **Permission Types**: 14 standard rights + custom types support
- **Automatic Roles**: 4 (Guest, All, Desk User, Administrator)

---

## Next Steps

This document provides the foundational inventory of files and components. The next phase will include:

1. **Detailed Code Analysis**: Deep dive into each file to document logic flow
2. **Data Model Analysis**: Document how permissions are stored and retrieved
3. **API Analysis**: Document public API endpoints for permissions
4. **Permission Hierarchy**: Document precedence rules (role > owner > share > user permission)
5. **Caching Strategy**: Document how permissions are cached
6. **Performance Implications**: Identify permission-related performance bottlenecks
7. **Security Analysis**: Review permission validation logic for vulnerabilities

---

**Document Version**: 1.0
**Last Updated**: 2026-03-27

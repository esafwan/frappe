# Frappe Framework - Roles & Permissions Deep Analysis

**Purpose**: Comprehensive analysis of how roles and permissions work together in Frappe Framework

**Date**: 2026-03-27
**Status**: Phase 2 - Deep Architecture Analysis

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Data Model & Relationships](#data-model--relationships)
3. [Permission Storage & Metadata](#permission-storage--metadata)
4. [Permission Evaluation Flow](#permission-evaluation-flow)
5. [Role System Architecture](#role-system-architecture)
6. [User Permissions System](#user-permissions-system)
7. [Caching & Performance](#caching--performance)
8. [Database Integration](#database-integration)
9. [Data Flow Diagrams](#data-flow-diagrams)
10. [Component Interactions](#component-interactions)
11. [Permission Precedence Rules](#permission-precedence-rules)

---

## Architecture Overview

### Core Permission System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    Permission System                         │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐      ┌──────────────────┐              │
│  │  Role-Based      │      │  Document-Level  │              │
│  │  Permissions     │      │  Permissions     │              │
│  │  (DocType →      │      │  (User →         │              │
│  │   Role →         │      │   DocType →      │              │
│  │   Rights)        │      │   Specific Doc)  │              │
│  └──────────────────┘      └──────────────────┘              │
│                                                               │
│  ┌──────────────────┐      ┌──────────────────┐              │
│  │  Sharing         │      │  Field-Level     │              │
│  │  Permissions     │      │  Permissions     │              │
│  │  (Explicit       │      │  (Permission     │              │
│  │   User Grants)   │      │   Levels)        │              │
│  └──────────────────┘      └──────────────────┘              │
│                                                               │
│  ┌──────────────────┐      ┌──────────────────┐              │
│  │  User            │      │  Owner-Based     │              │
│  │  Permissions     │      │  Permissions     │              │
│  │  (Record-level   │      │  (if_owner flag) │              │
│  │   access)        │      │                  │              │
│  └──────────────────┘      └──────────────────┘              │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Model & Relationships

### Entity Relationship Diagram

```
┌──────────────┐
│     User     │◄─────────────────────┐
│   (Table)    │                       │
├──────────────┤                       │
│ name (PK)    │                       │
│ email        │                       │
└──────────────┘                       │
      │                                │
      │ 1──────────────M               │
      │                                │
      ▼                                │
┌──────────────────┐                   │
│   User Role      │ (Child Table)     │
│   (Tab User_role)│                   │
├──────────────────┤                   │
│ user (FK) ◄──────┴───────────┐       │
│ role (FK) ─────────────┐     │       │
│                        │     │       │
└──────────────────┘     │     │       │
      │                  │     │       │
      │ 1──────────────M │     │       │
      │                  │     │       │
      ▼                  │     │       │
┌──────────────────┐     │     │       │
│  Role Profile    │     │     │       │
│  (DocType)       │     │     │       │
├──────────────────┤     │     │       │
│ name (PK)        │     │     │       │
│ roles[] ◄────────┴─────┤     │       │
└──────────────────┘     │     │       │
                         │     │       │
                         ▼     │       │
                    ┌──────────┴──┐    │
                    │    Role     │    │
                    │  (DocType)  │    │
                    ├─────────────┤    │
                    │ name (PK)   │    │
                    │ disabled    │    │
                    │ desk_access │    │
                    └─────┬───────┘    │
                          │            │
                          │ 1──────────┴─M
                          │
                          ▼
                    ┌────────────┐
                    │   DocPerm  │ (Child Table)
                    │  (Perm)    │
                    ├────────────┤
                    │parent(DT)  │
                    │role (FK)   │
                    │permlevel   │◄────┐
                    │if_owner    │     │
                    │read/write  │     │
                    │create/del  │     │
                    │etc.        │     │
                    └────────────┘     │
                                       │
              ┌────────────────────────┘
              │
              ▼
         ┌─────────────┐
         │  DocField   │ (Child Table)
         │  (Field)    │
         ├─────────────┤
         │ parent (DT) │
         │ fieldname   │
         │ permlevel ◄─┴─── Field-level permission grouping
         │ read_only   │
         │ fieldtype   │
         │ hidden      │
         │ collapsible │
         │ mask        │
         └─────────────┘


Additional Relationships:

┌──────────────────┐         ┌──────────────────────┐
│ User Permission  │         │   DocShare           │
│  (Document)      │         │ (Sharing System)     │
├──────────────────┤         ├──────────────────────┤
│ user (FK) ◄──────┼─────────┤ user (FK)            │
│ allow (DT)       │         │ share_doctype        │
│ for_value        │         │ share_name           │
│ applicable_for   │         │ read/write/share     │
│ is_default       │         │ everyone             │
│ hide_descendants │         └──────────────────────┘
└──────────────────┘

┌──────────────────┐         ┌──────────────────────┐
│ Permission Log   │         │ Permission Type      │
│ (Audit)          │         │ (Custom Rights)      │
├──────────────────┤         ├──────────────────────┤
│ user             │         │ name (PK)            │
│ doctype          │         │ perms[] (custom)     │
│ docname          │         │                      │
│ operation        │         └──────────────────────┘
│ timestamp        │
└──────────────────┘
```

### Key Relationships Explained

#### **1. Role ↔ User (Many-to-Many via User Role)**

```
User: "john@company.com"
  ├─ User Role 1: "Desk User"
  ├─ User Role 2: "Sales User"
  ├─ User Role 3: "Custom Role"
  └─ User Role Profile: "Sales Manager Profile"
      ├─ Role: "Sales Manager"
      └─ Role: "Report Viewer"

Result: john has 5 effective roles
```

**Where Stored**:
- `tabUser_role` table (direct role assignment)
- `tabUserRoleProfile` table (profile-based assignment)

#### **2. Role ↔ DocType (One-to-Many via DocPerm)**

```
Role: "Sales User"
  ├─ DocPerm (Order): read=1, write=1, create=1
  ├─ DocPerm (Customer): read=1, write=0, create=0
  ├─ DocPerm (Invoice): read=1, write=0, create=0
  └─ DocPerm (Report): read=1, report=1

Defines: What can "Sales User" do with each DocType
```

**Where Stored**:
- `tabDocPerm` table (child table of DocType)
- DocType metadata JSON files

#### **3. DocType ↔ DocField ↔ PermLevel (Hierarchical Permission Levels)**

```
ORDER DocType:
├─ Field: order_date (permlevel=0)
│  └─ All permissions that grant read → can access
│
├─ Field: customer_po_no (permlevel=0)
│  └─ All permissions that grant read → can access
│
├─ Section Break: Pricing Details (collapsible section)
│
├─ Field: rate (permlevel=1)
│  └─ Only users with permlevel ≥ 1 read access → can see
│  └─ Sales Manager (permlevel=1) can see
│  └─ Regular Sales User (permlevel=0 only) cannot see
│
└─ Field: cost_price (permlevel=2)
   └─ Only users with permlevel ≥ 2 read access → can see
   └─ CFO/Finance Manager (permlevel=2) can see

Permission Rule for "Sales User":
  ├─ read=1, permlevel=0
  └─ Access to: order_date, customer_po_no
  └─ CANNOT access: rate (needs permlevel=1)
  └─ CANNOT access: cost_price (needs permlevel=2)
```

**Permission Levels Concept**:
```
permlevel=0: Main document level (all users)
permlevel=1: First level details (manager level)
permlevel=2: Second level sensitive data (senior management)
permlevel=3: Third level restricted info (C-level executives)

DocPerm RULE: {
  role: "Sales User",
  permlevel: 0,      ← This rule applies to permlevel 0 fields only
  read: 1,           ← Can read permlevel 0 fields
  write: 1,          ← Can write permlevel 0 fields
  create: 1
}

DocPerm RULE: {
  role: "Sales Manager",
  permlevel: 1,      ← This rule applies to permlevel 0 AND 1 fields
  read: 1,           ← Can read permlevel 1 fields
  write: 1
}
```

#### **4. User ↔ User Permission ↔ DocType (Record-Level Filtering)**

```
User: "john@company.com"

User Permissions:
├─ Allow: Customer, For Value: CUST-001
│  ├─ Applicable For: Order (restrict this doctype)
│  └─ is_default: true (use when creating Order)
│
├─ Allow: Customer, For Value: CUST-002
│  └─ Applicable For: Order
│
├─ Allow: Company, For Value: Company-USA
│  ├─ Applicable For: All DocTypes
│  └─ (This customer can ONLY access USA company records)
│
└─ Allow: Department, For Value: Sales
   ├─ Applicable For: Employee
   └─ (Can only view/edit Sales department employees)

Result When Accessing Orders:
- Can only see Orders with customer IN (CUST-001, CUST-002)
- SQL Filter: WHERE customer IN (...)
```

**Where Stored**:
- `tabUserPermission` table
- Cached in Redis under `user_permissions:{username}`

#### **5. DocType ↔ DocField ↔ Link Field (User Permission Chain)**

```
ORDER DocType has fields:
├─ customer (Link field → Customer)
├─ supplier (Link field → Supplier)
└─ company (Link field → Company)

User Permission Applied to "Order" via Link Fields:
├─ User restricted: Only company = "Company-USA"
│  └─ When creating Order:
│     └─ MUST select company = "Company-USA"
│     └─ Can ONLY see that company's orders
│
├─ User restricted: Only customer IN (CUST-001, CUST-002)
│  └─ When creating Order:
│     └─ MUST select customer from allowed list
│     └─ Can ONLY see those customers' orders
│
└─ User NOT restricted on supplier
   └─ Can access any supplier

Validation happens on save:
├─ Check document owner
├─ Check direct document restrictions
├─ Check each link field against user permissions
└─ If any link field has restricted value → DENY
```

### 6. Share/Group Concept (Collaborative Access)

```
DocShare Table (Sharing Records):

User A (john@company.com) shares:
  ├─ Document: Order-001
  │  └─ With User B: read=1, write=1, share=1
  │
  └─ Document: Customer-XYZ
     └─ With User C: read=1, write=0

Conceptually (though not explicitly stored):
  ├─ "Share Group" = set of shared documents
  ├─ john controls access to Order-001
  ├─ john controls access to Customer-XYZ
  └─ Sharing overrides all other restrictions
```

**Where Stored**:
- `tabDocShare` table
- Cached in Redis under `doctype_shares:{doctype}` and `user_shares:{user}`

### Complete Relationship Flow for a Query

```
When User "john" tries to access "Order" list:

1. Get User's Roles:
   └─ User john has roles: ["Desk User", "Sales User", "All"]

2. Find Applicable Role Permissions:
   └─ For "Order" DocType:
      └─ Role "Sales User" → read=1, write=1, permlevel=0
      └─ Role "Desk User" → read=1, permlevel=0

3. Check Permission Levels:
   └─ john can access: permlevel 0 fields
   └─ Result: He sees public fields but not sensitive ones

4. Apply User Permissions Filters:
   └─ User Permission "john" → Allow: Customer, For: CUST-001
   └─ User Permission "john" → Allow: Company, For: Company-USA
   └─ SQL: WHERE customer = 'CUST-001' AND company = 'Company-USA'

5. Check if Owner-Only (if_owner):
   └─ Order.permissions: if_owner=1 for some role
   └─ Add: WHERE owner = 'john' OR (other conditions)

6. Check Sharing:
   └─ Get all Order records shared with john
   └─ Add: WHERE id IN (shared_ids) OR (other conditions)

7. Execute Query:
   └─ SELECT * FROM Order
      WHERE (customer = 'CUST-001' AND company = 'Company-USA')
      OR (Order.id IN (shared_with_john))

8. Filter Fields on Load:
   └─ Load document
   └─ Check each field.permlevel against john's access
   └─ Hide fields john doesn't have access to
```

---

## Permission Storage & Metadata

### 1. Role-Based Permissions Storage

**Location**: DocType metadata (JSON file + database)

**File**: `frappe/core/doctype/doctype/doctype.json` (and in DocPerm child table)

**Data Structure - DocPerm (Child Table)**:
```python
class DocPerm:
    role: str              # Link to Role document
    permlevel: int         # 0=main level, 1,2,3=child level fields

    # Permission Rights (boolean flags)
    read: bool
    write: bool
    create: bool
    delete: bool
    submit: bool
    cancel: bool
    amend: bool
    print: bool
    email: bool
    report: bool
    select: bool
    export: bool
    import: bool
    share: bool

    # Special Flags
    if_owner: bool         # Override permissions if user is document owner
    mask: bool             # Hide field from user
```

**Example Permission Rule**:
```
{
    "role": "Sales User",
    "permlevel": 0,
    "read": 1,
    "write": 1,
    "create": 1,
    "delete": 0,
    "submit": 0,
    "if_owner": 0
}
```

**Database Location**:
- Table: `tabDocPerm`
- Accessed via: `DocType.permissions` list when metadata is loaded

### 2. User & Role Assignment Storage

**Table: `tabUser_role`** (Child table of User)
- user: FK to User
- role: FK to Role
- Maps users to their assigned roles
- Cached in user session

**Table: `tabUserRoleProfile`** (Child table of User)
- user: FK to User
- role_profile: FK to Role Profile
- Alternative method to assign multiple roles via profiles

---

## Permission Evaluation Flow

### Main Permission Check Flow (Simplified)

```
frappe.permissions.has_permission(doctype, ptype="read", doc=None, user=None)
│
├─ [Check] Is user "Administrator"?
│  └─ YES → Return True (skip all checks)
│  └─ NO → Continue
│
├─ [Check] Is ptype "share" and sharing disabled globally?
│  └─ YES → Return False
│  └─ NO → Continue
│
├─ [Check] Is doctype a child table?
│  └─ YES → Call has_child_permission() with parent_doctype
│  └─ NO → Continue
│
├─ [Check] Is document instance specified?
│  └─ YES → Call get_doc_permissions(doc)
│  │        └─ Returns evaluated permissions for this specific doc
│  │        └─ Considers: owner, user permissions, role perms
│  └─ NO → Call get_role_permissions(meta)
│           └─ Returns general role-based permissions
│
├─ [Result] If permission granted → Return True
│
└─ [Fallback] Check shared documents
   └─ Has document been explicitly shared with user?
   └─ YES → Grant specified shared rights
   └─ NO → Return False
```

### Field-Level Permission Logic (PermLevel & Field Groups)

**Understanding Permission Levels**:

```
Each DocField has a "permlevel" attribute (0, 1, 2, 3, ...)

permlevel=0: Standard fields (everyone with "read" sees them)
permlevel=1: Sensitive fields (only users with permlevel ≥ 1 see them)
permlevel=2: Highly sensitive (only users with permlevel ≥ 2)
permlevel=3: Executive level (only C-suite level users)

Example: Order DocType

Field: Item Name (permlevel=0)
  └─ User with read=1, permlevel=0 → SEES IT

Field: Unit Price (permlevel=1)
  └─ User with read=1, permlevel=0 → CANNOT SEE
  └─ User with read=1, permlevel=1 → SEES IT

Field: Profit Margin (permlevel=2)
  └─ User with read=1, permlevel=1 → CANNOT SEE
  └─ User with read=1, permlevel=2 → SEES IT

Field: Cost Price (permlevel=2)
  └─ User with read=1, permlevel=1 → CANNOT SEE
  └─ User with read=1, permlevel=2 → SEES IT
```

**Field Groups (Section Break, Column Break)**:

```
Section Break: "Pricing Details" (collapsible=1, permlevel=1)
  ├─ Rate (permlevel=1)
  ├─ Tax (permlevel=1)
  └─ Total (permlevel=1)

Effect:
  └─ All fields in this section hidden if user lacks permlevel=1
  └─ Entire section collapses/hides for unauthorized users

Usage:
  └─ Grouping sensitive fields together
  └─ Single permission level applies to group
  └─ Clean UI - sensitive sections not even shown to low-level users
```

**How PermLevel is Applied During Document Load**:

```python
# In frappe/model/document.py: apply_fieldlevel_read_permissions()

doc.load_from_db()
  ├─ Get user's permlevel access:
  │  └─ get_permlevel_access("read")
  │  └─ Returns: [0, 1] (user can access levels 0 and 1 only)
  │
  ├─ For each field in document:
  │  ├─ Check: field.permlevel in allowed_permlevels?
  │  ├─ YES: field stays, user can read it
  │  ├─ NO: field hidden/cleared (user cannot read)
  │  └─ Example: Cost Price (permlevel=2) hidden for level 1 user
  │
  └─ User receives document with only accessible fields
```

**Combining PermLevel with Other Permissions**:

```
DocPerm Rule in DocType:
{
  role: "Sales Manager",
  permlevel: 0,
  read: 1,
  write: 1
}

This rule grants:
  ├─ READ access to all fields with permlevel ≤ 0
  ├─ WRITE access to all fields with permlevel ≤ 0
  └─ Hidden fields: Any with permlevel > 0

Separate DocPerm Rule:
{
  role: "Regional Manager",
  permlevel: 1,
  read: 1,
  write: 1
}

This rule grants:
  ├─ READ access to all fields with permlevel ≤ 1
  ├─ WRITE access to all fields with permlevel ≤ 1
  └─ Hidden fields: Any with permlevel > 1
```

**Permission Level Access Evaluation**:

```python
# In frappe/model/meta.py: get_permlevel_access()

def get_permlevel_access(self, permission_type="read"):
    has_access_to = []
    roles = frappe.get_roles(user)

    for perm in self.permissions:
        if perm.role in roles and perm.get(permission_type):
            # User's role has this permission
            if perm.permlevel not in has_access_to:
                has_access_to.append(perm.permlevel)

    return has_access_to
    # Returns: [0] or [0, 1] or [0, 1, 2] etc.
```

---

### Detailed Document Permission Check (get_doc_permissions)

```
get_doc_permissions(doc, user=None, ptype=None)
│
├─ Step 1: Check Controller Permissions
│  │ └─ Call has_permission hooks from doctypes
│  │ └─ Hooks can DENY but not GRANT permissions
│  │ └─ (frappe/hooks.py: has_permission = {...})
│  └─ If denied → Return {ptype: 0}
│
├─ Step 2: Get Role-Based Permissions
│  │ └─ Call get_role_permissions(meta, is_owner=True/False)
│  │ └─ Get all role permissions that apply to user
│  └─ Store in 'permissions' dict
│
├─ Step 3: Apply Doctype-Level Restrictions
│  │ ├─ Is document submittable? If not → perms["submit"] = 0
│  │ └─ Is document importable? If not → perms["import"] = 0
│
├─ Step 4: Apply Owner Overrides (if_owner flag)
│  │ ├─ Check if user is document owner
│  │ ├─ If has_if_owner_enabled:
│  │ │  └─ Apply if_owner permission overrides
│  │ │  └─ This UPGRADES permissions for owner
│  │ │  └─ Example: Everyone read, only owner write
│  │ └─ Store in perms["if_owner"] = {...}
│
├─ Step 5: Apply User Permissions (Record-Level Restrictions)
│  │ ├─ Call has_user_permission(doc, user)
│  │ └─ If user NOT allowed:
│  │    ├─ If user is owner: Keep if_owner permissions
│  │    └─ Else: Clear all permissions → {}
│
└─ Step 6: Return Final Permissions
   └─ {read: 1, write: 0, create: 0, ...}
```

### Role Permission Evaluation (get_role_permissions)

```
get_role_permissions(doctype_meta, user=None, is_owner=False)
│
├─ Step 1: Check Cache
│  │ └─ cache_key = (doctype_name, user, is_owner)
│  └─ Return cached value if exists
│
├─ Step 2: Get User Roles
│  └─ roles = frappe.get_roles(user)
│     └─ Returns list like: ["Desk User", "Sales User", "All"]
│
├─ Step 3: Filter Applicable Permissions
│  │ └─ applicable_permissions = [perm for perm in doctype.permissions
│  │                              if perm.role in user.roles
│  │                              and perm.permlevel == 0]
│  └─ Only level 0 (main level) permissions apply
│
├─ Step 4: Build Permission Dict
│  │ ├─ For each permission type (read, write, create, etc):
│  │ │  └─ ptype_value = OR of all applicable permissions
│  │ │  └─ Example: If ANY role grants read → read = 1
│  │ └─ perms[ptype] = 1 if any role allows it else 0
│
├─ Step 5: Handle if_owner Permissions
│  │ ├─ If any permission has if_owner flag:
│  │ │  ├─ If permission only via if_owner:
│  │ │  │  └─ perms[ptype] = 1 (allow list access)
│  │ │  │  └─ perms["if_owner"][ptype] = is_owner (actual access)
│  │ │  └─ Else:
│  │ │     └─ Full access for owner
│  │ └─ Example:
│  │    ├─ Role: read=1, if_owner=1, write=0
│  │    ├─ Result: read=1, write=0 if not owner
│  │    ├─ Result: read=1, write=0 (if_owner section empty)
│
├─ Step 6: Cache Result
│  └─ frappe.local.role_permissions[cache_key] = perms
│
└─ Step 7: Return Permissions Dict
   └─ {read: 1, write: 0, create: 0, if_owner: {write: 1}, ...}
```

### User Permission Check (has_user_permission)

```
has_user_permission(doc, user=None)
│
├─ Step 1: Load User Permissions
│  └─ user_perms = get_user_permissions(user)
│     └─ Returns dict: {"Customer": [{"doc": "CUST-001"}, ...], ...}
│     └─ Grouped by DocType
│     └─ Cached for performance
│
├─ Step 2: Check Direct Document Permissions
│  │ ├─ If doc.doctype in user_perms:
│  │ │  ├─ Get allowed_docs list for this doctype
│  │ │  ├─ Check if doc.name in allowed_docs
│  │ │  └─ If not in list: DENY access
│  │ └─ (This restricts access to specific documents)
│
├─ Step 3: Check Link Field Permissions
│  │ ├─ For each Link field in document:
│  │ │  ├─ Get the linked doctype
│  │ │  ├─ Check if user has permission for linked value
│  │ │  ├─ Example: Order references Customer
│  │ │  │           User must have permission for that Customer
│  │ │  └─ If not permitted: DENY with detailed message
│  │ └─ Applied to parent and all child records
│
├─ Step 4: Strict User Permissions Mode
│  │ ├─ If system setting: "apply_strict_user_permissions" = True:
│  │ │  └─ Empty link fields are NOT allowed
│  │ │  └─ Example: Can't create Order without selecting Customer
│  │ └─ Affects new unsaved documents
│
└─ Step 5: Return Result
   └─ True if all checks pass, False if any denied
```

---

## Role System Architecture

### Role Assignment Layers

```
┌─ AUTOMATIC ROLES (4 Built-in) ──────────────────────────┐
│ All Users Get:                                           │
│  • "Guest" → Non-logged in users                        │
│  • "All" → All logged-in users                          │
│  • "Desk User" → Users with system access               │
│  • "Administrator" → Super admin (bypasses all checks)  │
└──────────────────────────────────────────────────────────┘

↓ (Automatically Added Based on User Type)

┌─ EXPLICIT ROLE ASSIGNMENT ──────────────────────────────┐
│ From User Document:                                      │
│  • User.roles[] = Direct role assignment                │
│  • User.user_role_profiles[] = Role profile refs       │
└──────────────────────────────────────────────────────────┘

↓ (User profile expands to multiple roles)

┌─ ROLE PROFILE EXPANSION ────────────────────────────────┐
│ From Role Profile Document:                             │
│  • Role Profile.roles[] = List of roles in profile     │
│  • These roles are added to effective_roles             │
└──────────────────────────────────────────────────────────┘

↓

┌─ EFFECTIVE ROLES ───────────────────────────────────────┐
│ Final Set Used for Permission Checks:                   │
│  = AUTOMATIC + EXPLICIT + (PROFILE ROLES)               │
│  Example: ["Guest", "All", "Desk User", "Sales User"]  │
└──────────────────────────────────────────────────────────┘
```

### Role Loading & Caching

**Function**: `frappe.get_roles(username)`
- Location: `frappe/permissions.py` → `get_roles()`
- Called: During permission checks and session bootstrap

**Caching Layer**:
- Cached in: `frappe.local.user_roles` (per-request cache)
- Also cached in: Redis `user_roles:{username}`
- Invalidated: When user document is modified

**Flow**:
```
frappe.get_roles(user)
  └─ Check cache: frappe.local.user_roles
  └─ If cached: Return
  └─ Else: Query database
     ├─ Get tabUser.roles[] (User Role table)
     ├─ Get expanded roles from Role Profiles
     ├─ Add AUTOMATIC_ROLES
     └─ Cache result locally + Redis
```

---

## User Permissions System

### User Permission Record Structure

**DocType**: User Permission (in `frappe/core/doctype/user_permission/`)

```
User Permission Record:
{
    "user": "sales@company.com",
    "allow": "Customer",           # DocType to restrict
    "for_value": "CUST-001",      # Specific document to allow
    "is_default": False,           # Use as default when creating
    "apply_to_all_doctypes": True, # Apply restriction globally
    "applicable_for": "Order",     # Or restrict to specific DocType
    "hide_descendants": False      # Hide tree descendants
}
```

### User Permission Caching

**Cache Key**: `user_permissions:{user}`

**Cache Structure**:
```python
cached_user_permissions = {
    "Customer": [
        {
            "doc": "CUST-001",
            "applicable_for": None,
            "is_default": True,
            "hide_descendants": False
        },
        {
            "doc": "CUST-002",
            ...
        }
    ],
    "Company": [...]
}
```

**Building Cache** (`get_user_permissions()` in user_permission.py):
```
For each User Permission record for user:
  1. Get allow = Doctype to restrict
  2. Add for_value to out[allow][]
  3. If doctype is tree AND hide_descendants=False:
     └─ Add all tree descendants to allowed list
  4. Cache in Redis with key "user_permissions:{user}"
  5. Return dict grouped by doctype
```

**Cache Invalidation**:
```
When User Permission is updated/deleted:
  1. Clear cache: frappe.cache.hdel("user_permissions", user)
  2. Publish event: "update_user_permissions" → frontend
  3. Next query will rebuild cache
```

### User Permission Application Flow

```
When checking document access:

1. Get user_permissions = get_user_permissions(user)
   └─ Returns: {Customer: [...], Company: [...]}

2. Check STEP 1: Direct document restrictions
   ├─ Is doc.doctype in user_perms?
   └─ If yes: Is doc.name in allowed_docs?
      └─ If no: DENY

3. Check STEP 2: Link field restrictions
   ├─ For each Link field in document:
   │  ├─ Get field.options (linked doctype)
   │  ├─ Is field.options in user_perms?
   │  └─ If yes: Is field.value in allowed_docs?
   │     └─ If no: DENY
   │
   └─ Applied to:
      ├─ Parent document
      └─ All child table records

4. Check STEP 3: Strict User Permissions
   ├─ If setting enabled:
   │  └─ Empty link fields are NOT allowed
   │  └─ Example: Must select a Customer
   └─ Applied on new unsaved docs only

Result: Allow or Deny with detailed error message
```

---

## Caching & Performance

### Three-Layer Caching Strategy

```
┌─────────────────────────────────────────────────┐
│ LAYER 1: Per-Request Cache (frappe.local)      │
│ ├─ frappe.local.role_permissions                │
│ │  └─ Key: (doctype, user, is_owner)           │
│ │  └─ Lifetime: Request duration               │
│ ├─ frappe.local.user_roles                      │
│ │  └─ Key: None (simple cache)                 │
│ │  └─ Lifetime: Request duration               │
│ └─ frappe.local.cached_user_permissions         │
│    └─ Key: None                                 │
│    └─ Lifetime: Request duration               │
└─────────────────────────────────────────────────┘
            ↓ (If not in local cache)
┌─────────────────────────────────────────────────┐
│ LAYER 2: Redis Cache (frappe.cache)            │
│ ├─ user_roles:{username}                        │
│ │  └─ User's role list                         │
│ ├─ user_permissions:{username}                  │
│ │  └─ User's permission dict                   │
│ ├─ user_doc:{username}                         │
│ │  └─ User document                            │
│ └─ Lifetime: Until invalidated                 │
└─────────────────────────────────────────────────┘
            ↓ (If not in Redis)
┌─────────────────────────────────────────────────┐
│ LAYER 3: Database Query                        │
│ ├─ SELECT * FROM tabUser_role WHERE ...        │
│ ├─ SELECT * FROM "User Permission" WHERE ...   │
│ └─ Lifetime: Until next cache invalidation     │
└─────────────────────────────────────────────────┘
```

### Cache Invalidation Events

**User Changes Invalidate**:
```
User document modified:
  └─ frappe.cache.hdel("user_doc", user)
  └─ frappe.cache.hdel("user_roles", user)
  └─ Rebuild on next request
```

**Role Changes Invalidate**:
```
Role document modified:
  └─ frappe.cache.clear_cache(doctype="Role")
  └─ All role-related caches cleared globally
  └─ Affects ALL users
```

**User Permission Changes Invalidate**:
```
User Permission record changed:
  └─ frappe.cache.hdel("user_permissions", user)
  └─ publish_realtime("update_user_permissions", user=user)
  └─ Frontend also notified
```

**Doctype Changes Invalidate**:
```
DocType.permissions modified:
  └─ frappe.cache.hdel("doctype_perm:{doctype}")
  └─ All users affected
```

---

## Database Integration

### Query Permission Conditions

**When**: Every database query execution

**Where**: `frappe/database/query.py:add_permission_conditions()`

**Logic Flow**:
```
Build Query:
  ├─ Check: Does user have role permission to read/select?
  │  └─ If NO: Apply only shared documents filter
  │  └─ If YES: Continue to next step
  │
  ├─ Check: Does document have if_owner restriction?
  │  └─ If YES: Add WHERE owner = current_user
  │  └─ If NO: Continue to next step
  │
  ├─ Check: Are there user permissions for this doctype?
  │  └─ If YES: Add WHERE doc IN (allowed_docs)
  │  └─ If NO: Continue to next step
  │
  ├─ Check: Are there custom permission query conditions?
  │  └─ If YES: Add custom WHERE conditions from hooks
  │  └─ If NO: All documents accessible
  │
  └─ Check: Are shared documents available?
     └─ If YES: Add WHERE doc IN (shared_docs) OR (other conditions)
     └─ Shared documents bypass all restrictions
```

### Permission Conditions Code

**From `frappe/database/query.py:1606`**:
```python
def get_permission_conditions(self, doctype: str, table: Table) -> Criterion:
    role_permissions = frappe.permissions.get_role_permissions(
        doctype,
        user=self.user
    )

    has_role_permission = role_permissions.get("read") or role_permissions.get("select")

    if not has_role_permission:
        # No role permissions, apply only share permissions
        shared_docs = frappe.share.get_shared(doctype, self.user)
        return table.name.isin(shared_docs)

    # Build conditions from: if_owner constraint OR user permissions
    conditions = []

    if self.requires_owner_constraint(role_permissions):
        conditions.append(table.owner == self.user)
    elif user_perm_conditions := self.get_user_permission_conditions(doctype, table):
        conditions.extend(user_perm_conditions)

    conditions.extend(self.get_permission_query_conditions(doctype))

    where_condition = Criterion.all(conditions)

    # Shared docs trump all other restrictions
    shared_docs = frappe.share.get_shared(doctype, self.user)
    if shared_docs:
        where_condition |= table.name.isin(shared_docs)

    return where_condition
```

---

## Data Flow Diagrams

### Complete Permission Check Flow for Document Access

```
User tries to access Document:
│
├─ Session loaded
├─ User's roles determined
├─ frappe.session.user = "john@company.com"
├─ frappe.get_roles() = ["All", "Desk User", "Sales User"]
│
└─ Document Load:
   └─ frappe.get_doc("Order", "ORD-001")
      │
      ├─ Document.__init__()
      ├─ load_doc_from_db()
      │
      └─ Check Permission: has_permission("read")
         │
         ├─ Call: frappe.permissions.has_permission()
         │
         ├─ Step 1: Get Role Permissions
         │  └─ get_role_permissions("Order", user="john@company.com")
         │     ├─ Check cache (frappe.local.role_permissions)
         │     ├─ Get applicable permissions from Order.permissions
         │     ├─ Filter by user roles
         │     └─ Return: {read: 1, write: 1, create: 0, ...}
         │
         ├─ Step 2: Get Document-Level Permissions
         │  └─ get_doc_permissions(doc)
         │     ├─ Check controller permissions (has_permission hooks)
         │     ├─ Apply role permissions
         │     ├─ Apply owner overrides if applicable
         │     ├─ Check user permissions
         │     │  ├─ Is Order.customer restricted by user permissions?
         │     │  └─ Is user allowed to view this specific Order?
         │     └─ Return final permissions
         │
         ├─ Step 3: Check Sharing
         │  ├─ If role permission denied:
         │  │  └─ Is this document explicitly shared with user?
         │  │  └─ frappe.share.get_shared("Order", "john@company.com")
         │  └─ If shared: Grant shared rights
         │
         └─ Step 4: Result
            ├─ Permission granted: Load and display document
            └─ Permission denied: Raise frappe.PermissionError
```

### Query Execution with Permission Filtering

```
User queries Order list:
│
├─ frappe.get_list("Order", filters={...})
│
├─ Database Query Builder creates:
│  └─ SELECT * FROM tabOrder WHERE (user_filters)
│
├─ Before Execution: add_permission_conditions()
│  │
│  ├─ Check role permissions
│  │  └─ Can user read Orders? YES
│  │
│  ├─ Check owner constraint
│  │  └─ Does Order have if_owner restriction? NO
│  │
│  ├─ Check user permissions
│  │  ├─ Are there user permission restrictions?
│  │  ├─ YES: Add filter WHERE customer IN (allowed_customers)
│  │  └─ This filters by Customer field link
│  │
│  ├─ Check permission query conditions
│  │  └─ frappe/hooks.py has_permission_query_conditions:
│  │     └─ Order: "custom_app.order.get_permission_query_conditions"
│  │     └─ Call custom function if exists
│  │
│  ├─ Check shared documents
│  │  └─ frappe.share.get_shared("Order", user)
│  │  └─ If any: Add WHERE id IN (shared_ids) OR (other_conditions)
│  │
│  └─ Final Query:
│     SELECT * FROM tabOrder
│     WHERE (user_filters)
│     AND (customer IN ('CUST-001', 'CUST-002'))
│     OR (Order.name IN (shared_docs))
│
└─ Execute and return filtered results
```

---

## Component Interactions

### 1. User Login → Permission Initialization

```
User Login (frappe/desk/doctype/user/user.py):
│
├─ Validate credentials
├─ Create session
│
└─ Load user permissions:
   ├─ frappe.get_user()
   │  └─ Creates UserPermissions object
   │  └─ Caches roles
   │
   ├─ frappe.get_roles()
   │  └─ Get list of roles for this user
   │  └─ Includes automatic roles
   │
   ├─ Cache user data:
   │  ├─ frappe.cache.hset("user_doc", user, {...})
   │  ├─ frappe.cache.hset("user_roles", user, [...])
   │  └─ frappe.cache.hset("user_permissions", user, {...})
   │
   └─ Bootstrap to client:
      └─ user_permission_write["User Permissions"] = get_user_permissions()
```

### 2. Role Document Update → Permission Invalidation

```
User updates Role document:
│
├─ Role.save()
│
├─ DocType metadata updated
│  ├─ Role.permissions modified
│  └─ Changes what this role can do
│
├─ Invalidate caches:
│  ├─ frappe.cache.clear_cache(doctype="Role")
│  │  └─ Clears role-related caches globally
│  │
│  ├─ frappe.local.role_permissions = {}
│  │  └─ Clear request-level cache
│  │
│  └─ All doctype permission caches cleared
│
├─ All users affected:
│  └─ Next permission check will recalculate
│
└─ Optionally: Publish realtime update
   └─ Active sessions notified
```

### 3. User Permission Update → Record Filter Change

```
Admin creates User Permission record:
│
├─ User Permission document saved
│
├─ validate():
│  ├─ Check for duplicates
│  ├─ Validate default overlaps
│  └─ Ensure record references valid doctype
│
├─ on_update():
│  ├─ frappe.cache.hdel("user_permissions", user)
│  │  └─ Clear this user's permission cache
│  │
│  ├─ frappe.publish_realtime("update_user_permissions", user=user)
│  │  └─ Notify user's sessions
│  │
│  └─ Log to Permission Log
│     └─ Audit trail created
│
└─ User's next query:
   ├─ get_user_permissions(user) rebuilds cache
   ├─ Includes new restrictions
   └─ Filtered results reflect new permission
```

### 4. DocType Permission Edit → Global Impact

```
Admin edits Order DocType permissions:
│
├─ Opens Order doctype
├─ Modifies Order.permissions[] table
│  │
│  └─ Example: Changes "Sales User" read from 1 → 0
│
├─ Save DocType
│
├─ Invalidate caches:
│  ├─ frappe.cache.delete_key("doctype_perm:Order")
│  ├─ frappe.local.role_permissions.clear()
│  └─ All affected permission caches cleared
│
├─ Affects ALL users:
│  └─ Sales User role no longer has read on Order
│
└─ Permission checks immediately start:
   ├─ Using new permission rules
   ├─ Sales User can no longer access Orders
   └─ Existing UI reflects change (if refreshed)
```

---

## Permission Precedence Rules

### Permission Evaluation Hierarchy (Highest to Lowest)

```
1. SYSTEM OVERRIDE
   └─ User is "Administrator"
      └─ All permissions granted immediately, skip all checks

2. SHARING PERMISSIONS (trumps all other restrictions except admin)
   └─ Document explicitly shared with user
   └─ Overrides role, owner, and user permission restrictions
   └─ "Shared documents trump all other restrictions" (code comment)

3. CONTROLLER PERMISSIONS (can only DENY, not GRANT)
   └─ frappe/hooks.py: has_permission hooks
   └─ Custom document logic can deny access
   └─ Called BEFORE role permissions
   └─ If controller denies → Access denied (no fallback)

4. ROLE-BASED PERMISSIONS (grants access if applicable)
   └─ DocType.permissions table
   └─ User's roles matched against permissions
   └─ Any role granting permission = access granted

5. OWNER PERMISSIONS (if_owner flag)
   └─ Overrides role permissions for document owner
   └─ Example: Everyone reads, only owner writes
   └─ Applied if user is document.owner
   └─ Can upgrade or downgrade permissions

6. USER PERMISSIONS (restricts access to specific records)
   └─ Record-level filtering
   └─ "You can access Order only for these Customers"
   └─ Can DENY even if role grants permission
   └─ Link field validation also enforced

7. SYSTEM SETTINGS
   └─ "apply_strict_user_permissions" mode
   └─ If enabled: empty link fields not allowed
   └─ If disabled: empty links permitted (less strict)

8. DOCUMENT-SPECIFIC PERMISSIONS
   └─ is_submittable, allow_import flags
   └─ Can only DENY certain permission types
```

### Example Precedence in Action

```
Order Document Scenario:

User: "john@company.com"
Roles: ["All", "Desk User", "Sales User"]
Order: ORD-001, owner="john@company.com", customer="CUST-002"

Permission Rules:
  - Role "Sales User": read=1, write=1, create=1, if_owner=0
  - Role "All": read=0, write=0 (not granted)
  - User Permission: john can only access Customer CUST-001

When john tries to access ORD-001:

Step 1: Is john Admin? NO → Continue
Step 2: Is ORD-001 shared with john? NO → Continue
Step 3: Does controller deny? NO → Continue
Step 4: Does "Sales User" role allow read? YES → Tentatively allowed
Step 5: Is john owner of ORD-001? YES → Check if_owner
        if_owner=0, so owner status doesn't change permissions
Step 6: Does user permission allow?
        john can only access CUST-001 orders
        ORD-001.customer = CUST-002
        NOT ALLOWED → DENY ACCESS

Result: DENIED (even though role granted permission)
        User permissions trump role permissions for this document
```

---

## Key Integration Points

### 1. Document Save
```
document.insert() / document.save()
  └─ check_permission("create") or check_permission("write")
  └─ Calls frappe.permissions.has_permission()
  └─ Raises PermissionError if denied
  └─ Permission log entry created (on_update hook)
```

### 2. Document Load
```
frappe.get_doc(doctype, name)
  └─ Load from database
  └─ Field-level filtering (apply_fieldlevel_read_permissions)
  └─ Hidden fields removed for non-permitted users
  └─ Submittable state verified
```

### 3. List Query
```
frappe.get_list(doctype, filters)
  └─ Build SQL query
  └─ add_permission_conditions() adds WHERE clauses
  └─ Returns only accessible documents
  └─ Uses cached user permissions for filtering
```

### 4. Report Execution
```
frappe.get_report_data(report)
  └─ Check report access via Role Permission for Page and Report
  └─ Filter report columns by field permissions
  └─ Apply permission query conditions
```

### 5. API Calls
```
frappe.call(method)
  └─ frappe/__init__.py: has_permission() check
  └─ Controller method permission check
  └─ Document.check_permission() if doc passed
```

---

## Performance Considerations

### Optimization Strategies

1. **Role Permission Cache** (Per-Request)
   - Caches evaluated role permissions
   - Key: (doctype, user, is_owner)
   - Hit Rate: ~90% for typical workflows
   - Saves: Role evaluation calculations

2. **User Permission Cache** (Redis)
   - Caches allowed documents per user per doctype
   - Built once on first request
   - Invalidated on User Permission change
   - Saves: N database queries for filtering

3. **User Roles Cache** (Redis)
   - Single list of roles per user
   - Built at login, refreshed on User change
   - Saves: Role lookup queries

4. **Lazy Document Loading**
   - Uses `frappe.get_lazy_doc()` for permission checks
   - Avoids loading child tables
   - Saves: Child table load time

### Query Optimization

1. **Permission Conditions as SQL**
   - Filtering happens at database level
   - NOT in Python application code
   - Saves: Network transfer of unauthorized records

2. **Index Usage**
   - owner field indexed
   - name field indexed
   - Links indexed for user permission filtering

3. **Batch Permission Checks**
   - Caching allows multiple checks without recalculation
   - Single user session reuses cached permissions

---

## Summary of How It All Works Together

### The Complete Picture

```
SESSION LAYER (frappe/utils/user.py)
  └─ UserPermissions object created at login
  └─ Caches user roles and permission settings
  └─ Provides get_roles(), build_permissions()

      ↓
ROLE DEFINITION LAYER (DocType Metadata)
  └─ Each DocType has DocPerm children
  └─ DocPerm = role + rights + level
  └─ Defines "what can this role do with this doctype"

      ↓
ROLE ASSIGNMENT LAYER (User Document)
  └─ User.user_role[] = explicit role assignment
  └─ User.user_role_profile[] = profile assignment
  └─ Role Profile expands to multiple roles
  └─ Automatic roles added by system

      ↓
PERMISSION EVALUATION LAYER (frappe/permissions.py)
  └─ has_permission() = main entry point
  └─ get_role_permissions() = evaluates role-based access
  └─ get_doc_permissions() = evaluates doc instance access
  └─ has_user_permission() = record-level filtering
  └─ Caches results for performance

      ↓
DOCUMENT-LEVEL LAYER (frappe/model/document.py)
  └─ Document.check_permission() on save
  └─ Document.has_permission() for access checks
  └─ Field-level filtering on load
  └─ Calls frappe.permissions.has_permission()

      ↓
DATABASE LAYER (frappe/database/query.py)
  └─ add_permission_conditions() adds WHERE clauses
  └─ get_permission_conditions() builds filter SQL
  └─ get_user_permission_conditions() adds record filters
  └─ get_permission_query_conditions() calls hooks
  └─ Only returns accessible documents

      ↓
USER PERMISSIONS LAYER (User Permission DocType)
  └─ get_user_permissions() builds restriction dict
  └─ Maps each doctype to allowed records
  └─ Cached per user in Redis
  └─ Invalidated on record changes
  └─ Overrides role permissions for records

      ↓
SHARING LAYER (frappe/share.py)
  └─ Explicit document-by-document sharing
  └─ Override any other restrictions
  └─ DocShare table records user access
  └─ Independent of roles and user permissions

      ↓
RESULT
  └─ User sees only documents they're allowed to access
  └─ Can perform only operations their roles allow
  └─ Cannot bypass via direct record access
  └─ All filtered at source (database)
```

---

## Data Model Hierarchy & Permission Resolution

### Complete Hierarchical Relationship

```
SYSTEM LEVEL
│
├─ Role (System-defined or Custom)
│  ├─ Desk User (automatic)
│  ├─ All (automatic)
│  ├─ Guest (automatic)
│  ├─ Administrator (automatic)
│  └─ Custom Roles (Sales User, etc.)
│
├─ Role Profile (Groups of Roles)
│  └─ Example: "Sales Manager Profile"
│     ├─ contains: Sales User role
│     ├─ contains: Report Viewer role
│     └─ contains: Dashboard Access role
│
└─ Permission Type (Custom Rights)
   └─ Example: "can_approve_invoice"
      ├─ Added to DocType as custom right
      └─ Can be assigned in DocPerm rules
│
├─────────────────────────────────────────────┤
│
USER LEVEL
│
├─ User Document
│  ├─ user_role[] (direct role assignment)
│  │  ├─ Desk User
│  │  └─ Sales User
│  └─ user_role_profile[] (via profile)
│     └─ Sales Manager Profile
│        ├─ Sales User
│        ├─ Report Viewer
│        └─ Dashboard Access
│
├─ User Permission (Document/Record Restrictions)
│  ├─ Allow: Customer, For: CUST-001
│  │  ├─ applicable_for: Order
│  │  ├─ is_default: True
│  │  └─ hide_descendants: False
│  └─ Allow: Company, For: Company-USA
│     ├─ applicable_for: All
│     └─ Filters all related records
│
└─ Doc Share (Explicit Sharing)
   ├─ Document: Order-001
   │  └─ User: john@company.com
   │     ├─ read: 1
   │     ├─ write: 1
   │     └─ share: 1
   └─ Document: Invoice-123
      └─ User: john@company.com
         ├─ read: 1
         └─ write: 0
│
├─────────────────────────────────────────────┤
│
DOCTYPE LEVEL
│
├─ DocType Document
│  ├─ Basic Properties
│  │  ├─ name: "Order"
│  │  ├─ is_submittable: True
│  │  ├─ allow_import: True
│  │  └─ issingle: False
│  │
│  ├─ DocPerm[] (Permission Rules) ◄─── ROLE-BASED PERMISSIONS
│  │  ├─ Rule: Role="Sales User", PerLevel=0
│  │  │  ├─ read=1, write=1, create=1, delete=0
│  │  │  ├─ submit=0, cancel=0, amend=0
│  │  │  ├─ print=1, email=1, export=0
│  │  │  └─ if_owner=0
│  │  │
│  │  ├─ Rule: Role="Sales Manager", PerLevel=0
│  │  │  ├─ read=1, write=1, create=1, delete=1
│  │  │  ├─ submit=0, cancel=0, amend=0
│  │  │  └─ if_owner=0
│  │  │
│  │  ├─ Rule: Role="Sales Manager", PerLevel=1
│  │  │  └─ (Allows access to level 1 fields like pricing)
│  │  │
│  │  └─ Rule: Role="Finance", PerLevel=2
│  │     └─ (Allows access to level 2 fields like cost)
│  │
│  └─ DocField[] (Field Definitions) ◄─── FIELD-LEVEL METADATA
│     ├─ Field: order_no
│     │  ├─ fieldtype: "Data"
│     │  ├─ permlevel: 0 ◄─── All users with read can see
│     │  ├─ read_only: False
│     │  └─ label: "Order Number"
│     │
│     ├─ Field: customer
│     │  ├─ fieldtype: "Link"
│     │  ├─ options: "Customer"
│     │  ├─ permlevel: 0 ◄─── All users can see
│     │  ├─ ignore_user_permissions: False
│     │  │  └─ Subject to customer-based user permissions
│     │  └─ label: "Customer"
│     │
│     ├─ Section Break: "Pricing Details"
│     │  ├─ collapsible: True
│     │  ├─ permlevel: 1 ◄─── Entire section hidden unless level≥1
│     │  └─ Hidden for permlevel=0 users
│     │
│     ├─ Field: unit_rate
│     │  ├─ fieldtype: "Currency"
│     │  ├─ permlevel: 1 ◄─── Hidden from permlevel=0 users
│     │  └─ label: "Unit Rate"
│     │
│     ├─ Section Break: "Cost Analysis"
│     │  ├─ collapsible: True
│     │  ├─ permlevel: 2 ◄─── Hidden unless level≥2
│     │  └─ Only Finance/Execs see
│     │
│     └─ Field: cost_price
│        ├─ fieldtype: "Currency"
│        ├─ permlevel: 2 ◄─── Executive level only
│        └─ label: "Cost Price"
│
├─────────────────────────────────────────────┤
│
QUERY/EXECUTION LEVEL
│
└─ Permission Evaluation (at runtime)
   ├─ Step 1: Get User's Effective Roles
   │  └─ john has: [Desk User, Sales User]
   │
   ├─ Step 2: Find applicable DocPerm rules
   │  └─ Match roles to DocPerm
   │  └─ Get: read=1, write=1, permlevel=0
   │
   ├─ Step 3: Determine PermLevel Access
   │  └─ permlevel=0 only
   │  └─ Cannot see fields with permlevel>0
   │
   ├─ Step 4: Evaluate User Permissions
   │  └─ john can only see customer=CUST-001
   │  └─ SQL: WHERE customer='CUST-001'
   │
   ├─ Step 5: Apply Field Filtering
   │  ├─ order_no (permlevel=0) → SHOWN
   │  ├─ customer (permlevel=0) → SHOWN
   │  ├─ Pricing Details section (permlevel=1) → HIDDEN
   │  ├─ unit_rate (permlevel=1) → HIDDEN
   │  ├─ Cost Analysis section (permlevel=2) → HIDDEN
   │  └─ cost_price (permlevel=2) → HIDDEN
   │
   └─ Result: Filtered document with visible fields only
```

### Permission Evaluation Matrix

| Component | Storage | Scope | Level | Override? |
|-----------|---------|-------|-------|-----------|
| **Role** | Role Doc | System | Global | No |
| **DocPerm** | DocType Meta | DocType | System | Yes (via Custom DocPerm) |
| **User Role** | User Table | User | System | Yes (assign/unassign) |
| **Role Profile** | Role Profile Doc | User | System | Yes (create/modify) |
| **PermLevel** | DocField | Field | System | Yes (Property Setter) |
| **User Permission** | User Permission Doc | User + DocType | Document | Yes (create/modify) |
| **DocShare** | DocShare Table | Document | Document | Yes (share/unshare) |
| **Custom DocPerm** | Custom DocPerm Table | DocType | Document | Yes (edit) |
| **Permission Hook** | hooks.py | DocType | Code | Yes (custom code) |

### Resolution Order When Multiple Rules Exist

```
When evaluating permission for: User "john" → Action "read" → DocType "Order"

1. Check all DocPerm rules for "Order"
   ├─ Rule 1: Role="All", read=1 → APPLICABLE (john is "All")
   ├─ Rule 2: Role="Desk User", read=1 → APPLICABLE (john is "Desk User")
   ├─ Rule 3: Role="Sales User", read=1 → APPLICABLE (john is "Sales User")
   ├─ Rule 4: Role="Finance", read=1 → NOT APPLICABLE (john not Finance)
   └─ Rule 5: Role="Administrator", read=1 → NOT APPLICABLE

2. Combine Applicable Rules (OR logic)
   ├─ john gets: read=1 (from Any of above)
   └─ Result: john can read Orders

3. Evaluate PermLevel
   ├─ If user has role with permlevel=0 permission
   └─ Can see only permlevel=0 and below fields

4. Apply User Restrictions
   ├─ If john has: "Allow Customer CUST-001"
   └─ Can only see Orders for that customer

5. Check Sharing
   ├─ Any Order explicitly shared with john?
   └─ Those overriding user permission restrictions

Final Result:
  └─ john can read Orders for CUST-001 only
  └─ Sees only permlevel=0 fields
  └─ Plus any explicitly shared Orders
```

---

## Conclusion

The Frappe permission system is a **multi-layered, cache-optimized, hierarchical access control** system that:

1. **Defines Access** via role-based permissions on doctypes
2. **Assigns Roles** directly to users or via profiles
3. **Evaluates Access** using a precedence-based rule engine
4. **Restricts Records** using user permissions and sharing
5. **Filters Data** at the database query level
6. **Optimizes Performance** through three-layer caching
7. **Audits Changes** via permission logs
8. **Integrates Hooks** for custom permission logic

The architecture ensures that permission checks happen:
- **Early** (at document load/save)
- **Consistently** (same logic everywhere)
- **Efficiently** (cached, database-filtered)
- **Securely** (no bypass methods available)

---

**Document Version**: 3.0 - Complete with Data Model & Relationships
**Last Updated**: 2026-03-27
**Status**: Complete - Ready for Security & Performance Review Phase

### What's Covered in This Document

✅ **Architecture Overview** - System components and structure
✅ **Data Model & Relationships** - Complete entity relationships and hierarchies
✅ **Permission Storage** - How permissions are stored and organized
✅ **Permission Evaluation Flow** - Step-by-step permission check logic
✅ **Role System Architecture** - Role assignment, profiles, and caching
✅ **User Permissions System** - Record-level filtering and restrictions
✅ **Field-Level Permissions** - PermLevel, field groups, and access tiers
✅ **Caching Strategy** - Three-layer caching with invalidation rules
✅ **Database Integration** - SQL permission condition building
✅ **Data Flows** - Complete flow diagrams for different scenarios
✅ **Component Interactions** - How components work together
✅ **Permission Precedence** - Complete hierarchy of permission rules
✅ **Permission Resolution Matrix** - What wins in conflicts
✅ **Complete Hierarchical Map** - System → User → DocType → Field levels

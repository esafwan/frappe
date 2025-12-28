# Custom Field Documentation

## Overview

Custom Fields in Frappe allow users to extend standard DocTypes with additional fields without modifying the core DocType definition. Custom fields are stored separately from the DocType JSON and are dynamically merged into the DocType metadata when loaded. This enables customization of standard DocTypes while maintaining upgradability.

**Key Concept**: Custom fields are not part of the DocType JSON file but are stored in the `tabCustom Field` database table and automatically merged into DocType metadata during runtime.

---

## Table of Contents

1. [Architecture & Storage](#architecture--storage)
2. [Custom Field Document Structure](#custom-field-document-structure)
3. [Lifecycle & Workflow](#lifecycle--workflow)
4. [Creation Methods](#creation-methods)
5. [Metadata Loading & Merging](#metadata-loading--merging)
6. [Database Schema Synchronization](#database-schema-synchronization)
7. [Field Ordering & Positioning](#field-ordering--positioning)
8. [Custom Apps Integration](#custom-apps-integration)
9. [API Reference](#api-reference)
10. [Restrictions & Limitations](#restrictions--limitations)
11. [Developer Mode Behavior](#developer-mode-behavior)
12. [Best Practices](#best-practices)

---

## Architecture & Storage

### Storage Location

Custom fields are stored in the `tabCustom Field` database table, which is a standard Frappe DocType. Each custom field record represents a field that extends a target DocType.

**File**: `frappe/custom/doctype/custom_field/custom_field.json`  
**Database Table**: `tabCustom Field`

### Key Fields in Custom Field DocType

The Custom Field DocType contains all standard DocField properties plus:

- `dt` (Link to DocType): The target DocType this field extends
- `fieldname`: The name of the field (auto-generated with `custom_` prefix)
- `insert_after`: Controls field positioning
- `is_system_generated`: Flag indicating if created programmatically
- `is_virtual`: Flag for virtual fields (no DB column)

**Reference**: `frappe/custom/doctype/custom_field/custom_field.json` (lines 1-509)

---

## Custom Field Document Structure

### Core Class

**File**: `frappe/custom/doctype/custom_field/custom_field.py`  
**Class**: `CustomField(Document)` (line 16)

### Key Methods

#### 1. `autoname()` (lines 122-124)
```python
def autoname(self):
    self.set_fieldname()
    self.name = self.dt + "-" + self.fieldname
```
- Automatically generates the document name as `{doctype}-{fieldname}`
- Ensures fieldname is set before naming

#### 2. `set_fieldname()` (lines 126-157)
```python
def set_fieldname(self):
    restricted = ("name", "parent", "creation", "modified", ...)
    if not self.fieldname:
        # Generate from label
        self.fieldname = "custom_" + scrubbed_label
    self.fieldname = self.fieldname.lower()
```
- Generates fieldname from label if not provided
- Prefixes with `custom_` to avoid conflicts
- Converts to lowercase
- Handles restricted fieldnames

**Reference**: `frappe/custom/doctype/custom_field/custom_field.py:126-157`

#### 3. `validate()` (lines 162-202)
- Checks for fieldname conflicts with existing fields
- Validates `insert_after` positioning
- Prevents fieldtype changes for non-virtual fields (unless allowed)
- Validates translatable field support

**Reference**: `frappe/custom/doctype/custom_field/custom_field.py:162-202`

#### 4. `on_update()` (lines 204-214)
```python
def on_update(self):
    if not self.flags.ignore_validate:
        validate_fields_for_doctype(self.dt)
    if not frappe.flags.in_create_custom_fields:
        frappe.clear_cache(doctype=self.dt)
        frappe.db.updatedb(self.dt)
```
- Validates all fields for the doctype
- Clears metadata cache
- Updates database schema (adds/modifies column)

**Reference**: `frappe/custom/doctype/custom_field/custom_field.py:204-214`

#### 5. `on_trash()` (lines 216-239)
- Prevents deletion of Administrator-owned fields by non-admins
- Deletes associated property setters
- Updates doctype layouts
- Clears metadata cache

**Reference**: `frappe/custom/doctype/custom_field/custom_field.py:216-239`

---

## Lifecycle & Workflow

### Creation Flow

1. **User/Code Creates Custom Field Document**
   - Sets `dt` (target DocType), `label`, `fieldtype`, etc.
   - `before_insert()` hook sets fieldname (line 159-160)
   - `autoname()` generates document name (line 122-124)

2. **Validation**
   - `validate()` checks conflicts, positioning, fieldtype changes (line 162-202)
   - Fieldname uniqueness checked against existing fields

3. **Insertion**
   - Document saved to `tabCustom Field` table
   - `on_update()` hook triggered (line 204-214)

4. **Schema Update**
   - `frappe.db.updatedb(self.dt)` called (line 214)
   - Database column created/modified if not virtual

5. **Cache Invalidation**
   - Metadata cache cleared for target DocType (line 213)
   - Next metadata load will include the new field

### Update Flow

1. Field properties modified
2. `validate()` ensures fieldtype changes are allowed
3. `on_update()` syncs schema changes
4. Cache cleared, metadata reloaded

### Deletion Flow

1. `on_trash()` validates permissions (line 216-239)
2. Property setters deleted (line 226)
3. DocType layouts updated (lines 228-237)
4. Cache cleared
5. Database column remains (manual cleanup may be needed)

---

## Creation Methods

### 1. Via UI (Customize Form)

Users can create custom fields through the Frappe UI:
- Navigate to Customize Form
- Select DocType
- Add custom field
- Configure properties

**Frontend**: `frappe/custom/doctype/custom_field/custom_field.js` (lines 1-152)

### 2. Via Python API - Single Field

**Function**: `create_custom_field()`  
**Location**: `frappe/custom/doctype/custom_field/custom_field.py:293-311`

```python
def create_custom_field(doctype, df, ignore_validate=False, is_system_generated=True):
    """
    Create a single custom field
    
    Args:
        doctype: Target DocType name
        df: Field definition dict
        ignore_validate: Skip validation
        is_system_generated: Mark as system generated
    """
```

**Example**:
```python
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

create_custom_field("Customer", {
    "fieldname": "custom_industry",
    "label": "Industry",
    "fieldtype": "Data",
    "insert_after": "customer_name"
})
```

**Reference**: `frappe/custom/doctype/custom_field/custom_field.py:293-311`

### 3. Via Python API - Multiple Fields

**Function**: `create_custom_fields()`  
**Location**: `frappe/custom/doctype/custom_field/custom_field.py:314-380`

```python
def create_custom_fields(custom_fields: dict, ignore_validate=False, update=True):
    """
    Add / update multiple custom fields
    
    :param custom_fields: example {'Sales Invoice': [dict(fieldname='test')]}
    """
```

**Example**:
```python
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

create_custom_fields({
    "Sales Invoice": [
        {"fieldname": "custom_po_number", "label": "PO Number", "fieldtype": "Data"},
        {"fieldname": "custom_delivery_date", "label": "Delivery Date", "fieldtype": "Date"}
    ],
    ("Customer", "Supplier"): [
        {"fieldname": "custom_tax_id", "label": "Tax ID", "fieldtype": "Data"}
    ]
})
```

**Key Features**:
- Supports multiple doctypes (tuple syntax)
- Handles updates if field exists
- Batch processing with `frappe.flags.in_create_custom_fields` (line 328)
- Updates schema only once per doctype (lines 375-377)

**Reference**: `frappe/custom/doctype/custom_field/custom_field.py:314-380`

### 4. Via Custom App JSON Files

Custom fields can be defined in JSON files within custom app modules:

**Location**: `{app}/{module}/custom/{doctype}.json`

**Structure**:
```json
{
    "doctype": "Customer",
    "custom_fields": [
        {
            "fieldname": "custom_industry",
            "label": "Industry",
            "fieldtype": "Data",
            "insert_after": "customer_name"
        }
    ],
    "sync_on_migrate": true
}
```

**Sync Function**: `sync_customizations()`  
**Location**: `frappe/modules/utils.py:100-119`

**Sync Logic**: `sync_customizations_for_doctype()`  
**Location**: `frappe/modules/utils.py:122-194`

**Process**:
1. Scans `{app}/{module}/custom/` folders (line 110)
2. Loads JSON files (line 114-115)
3. Checks `sync_on_migrate` flag (line 116)
4. Inserts/updates custom fields (lines 141-153)
5. Updates database schema (line 193)

**Reference**: 
- `frappe/modules/utils.py:100-119` (sync_customizations)
- `frappe/modules/utils.py:122-194` (sync_customizations_for_doctype)
- `frappe/modules/utils.py:141-153` (Custom Field sync logic)

### 5. Via Database Direct Insert

Custom fields can be inserted directly into `tabCustom Field` table, but this is not recommended as it bypasses validation and schema updates.

---

## Metadata Loading & Merging

### Meta Class Processing

When a DocType metadata is loaded, custom fields are automatically merged:

**File**: `frappe/model/meta.py`  
**Class**: `Meta` (line 125)

**Process Flow** (line 161-175):
```python
def process(self):
    self.add_custom_fields()      # Merge custom fields
    self.apply_property_setters()  # Apply property setters
    self.init_field_caches()       # Build field maps
    self.sort_fields()             # Order fields
    self.get_valid_columns()       # Validate columns
    self.set_custom_permissions()  # Apply permissions
    self.add_custom_links_and_actions()  # Add custom links
    self.check_if_large_table()    # Performance check
```

### Adding Custom Fields to Metadata

**Method**: `add_custom_fields()`  
**Location**: `frappe/model/meta.py:399-415`

```python
def add_custom_fields(self):
    if not frappe.db.table_exists("Custom Field"):
        return
    
    custom_fields = frappe.db.get_values(
        "Custom Field",
        filters={"dt": self.name},
        fieldname="*",
        as_dict=True,
        order_by="idx",
        update={"is_custom_field": 1},  # Mark as custom field
    )
    
    if not custom_fields:
        return
    
    self.extend("fields", custom_fields)  # Merge into fields list
```

**Key Points**:
- Fetches all custom fields for the doctype (line 403-410)
- Marks each field with `is_custom_field: 1` (line 409)
- Orders by `idx` (line 408)
- Extends the `fields` list (line 415)

**Reference**: `frappe/model/meta.py:399-415`

### Field Identification

Custom fields are identified by the `is_custom_field` attribute:

**Method**: `get_custom_fields()`  
**Location**: `frappe/model/meta.py:363-364`

```python
def get_custom_fields(self):
    return [d for d in self.fields if getattr(d, "is_custom_field", False)]
```

**Reference**: `frappe/model/meta.py:363-364`

---

## Database Schema Synchronization

### Schema Update Trigger

When a custom field is created/updated, the database schema is synchronized:

**Trigger**: `on_update()` hook calls `frappe.db.updatedb(self.dt)`  
**Location**: `frappe/custom/doctype/custom_field/custom_field.py:214`

### Database Update Process

**Method**: `updatedb()`  
**Location**: `frappe/database/mariadb/database.py:450-466`

```python
def updatedb(self, doctype, meta=None):
    """
    Syncs a DocType to the table
    * creates if required
    * updates columns
    * updates indices
    """
    res = self.sql("select issingle from `tabDocType` where name=%s", (doctype,))
    if not res[0][0]:  # Not a single doctype
        db_table = MariaDBTable(doctype, meta)
        db_table.validate()
        db_table.sync()  # Sync schema
        self.commit()
```

**Reference**: `frappe/database/mariadb/database.py:450-466`

### Schema Sync Implementation

**Class**: `DBTable`  
**File**: `frappe/database/schema.py`  
**Method**: `sync()` (line 40)

**Process**:
1. `get_columns_from_docfields()` - Loads columns from metadata including custom fields (line 76-106)
2. Compares with existing database columns
3. Generates ALTER TABLE statements for:
   - New columns (add_column)
   - Type changes (change_type)
   - Nullability changes (change_nullability)
   - Index additions (add_index)
   - Unique constraints (add_unique)

**Key Method**: `get_columns_from_docfields()`  
**Location**: `frappe/database/schema.py:76-106`

```python
def get_columns_from_docfields(self):
    """
    get columns from docfields and custom fields
    """
    fields = self.meta.get_fieldnames_with_value(with_field_meta=True)
    # ... processes all fields including custom fields
    for field in fields:
        if field.get("is_virtual"):
            continue
        self.columns[field.get("fieldname")] = DbColumn(...)
```

**Reference**: `frappe/database/schema.py:76-106`

### Virtual Fields

Custom fields with `is_virtual: 1` do not create database columns. They are computed at runtime and only exist in metadata.

**Check**: `frappe/database/schema.py:92-93`

---

## Field Ordering & Positioning

### Insert After Mechanism

Custom fields use the `insert_after` property to control positioning:

**Property**: `insert_after` - Fieldname of the field after which to insert

**Auto-calculation**: If `insert_after == "append"`, it's set to the last field  
**Location**: `frappe/custom/doctype/custom_field/custom_field.py:180-181`

### Field Sorting

**Method**: `sort_fields()`  
**Location**: `frappe/model/meta.py:518-590`

**Priority Order**:
1. `field_order` property setter (highest priority)
2. `insert_after` for custom fields
3. Default field order

**Custom Field Sorting Logic** (lines 570-585):
```python
elif target_position := getattr(field, "insert_after", None):
    # Handle Section/Column Break positioning
    if field.fieldtype in ["Section Break", "Column Break"]:
        # Find next break and adjust position
    insertion_map.setdefault(target_position, []).append(field.fieldname)
else:
    # If custom field is at the top, insert after is None
    field_order.insert(0, field.fieldname)
```

**Reference**: `frappe/model/meta.py:518-590`

### Index Calculation

**Location**: `frappe/custom/doctype/custom_field/custom_field.py:183-184`

```python
if self.insert_after and self.insert_after in fieldnames:
    self.idx = fieldnames.index(self.insert_after) + 1
```

---

## Custom Apps Integration

### Export Custom Fields

**Function**: `export_doc()`  
**Location**: `frappe/modules/utils.py:58-99`

Custom fields can be exported to custom app folders:

```python
custom = {
    "custom_fields": frappe.get_all(
        "Custom Field", 
        fields="*", 
        filters={"dt": doctype}, 
        order_by="name"
    ),
    # ... other customizations
}
```

**Reference**: `frappe/modules/utils.py:68`

### Import/Sync Custom Fields

**Function**: `sync_customizations()`  
**Location**: `frappe/modules/utils.py:100-119`

**Process**:
1. Scans all installed apps (line 106)
2. Checks `{app}/{module}/custom/` folders (line 110)
3. Loads JSON files (line 114)
4. Syncs if `sync_on_migrate: true` or during install (lines 116-119)

**Reference**: `frappe/modules/utils.py:100-119`

### Sync Logic for Custom Fields

**Location**: `frappe/modules/utils.py:141-153`

```python
case "Custom Field":
    for d in data[key]:
        field = frappe.db.get_value(
            "Custom Field", {"dt": doc_type, "fieldname": d["fieldname"]}
        )
        if not field:
            d["owner"] = "Administrator"
            _insert(d)  # Insert new field
        else:
            custom_field = frappe.get_doc("Custom Field", field)
            custom_field.flags.ignore_validate = True
            custom_field.update(d)
            custom_field.db_update()  # Update existing
```

**Key Points**:
- Checks if field exists (line 143-144)
- Inserts if new (line 147-148)
- Updates if exists (line 150-153)
- Sets owner to Administrator (line 147)
- Skips validation during sync (line 151)

**Reference**: `frappe/modules/utils.py:141-153`

---

## API Reference

### Core Functions

#### `create_custom_field_if_values_exist(doctype, df)`

Creates a custom field only if the column exists in the database and has non-empty values.

**Parameters**:
- `doctype`: Target DocType name
- `df`: Field definition dictionary

**Use Case**: Useful for migrations where a column was added directly to the database and needs to be registered as a custom field.

**Location**: `frappe/custom/doctype/custom_field/custom_field.py:285-290`

#### `create_custom_field(doctype, df, ignore_validate=False, is_system_generated=True)`

Creates a single custom field.

**Parameters**:
- `doctype`: Target DocType name
- `df`: Field definition dictionary
- `ignore_validate`: Skip validation (default: False)
- `is_system_generated`: Mark as system generated (default: True)

**Returns**: CustomField document or None if already exists

**Location**: `frappe/custom/doctype/custom_field/custom_field.py:293-311`

#### `create_custom_fields(custom_fields: dict, ignore_validate=False, update=True)`

Creates/updates multiple custom fields.

**Parameters**:
- `custom_fields`: Dict mapping doctype(s) to field lists
  - Single doctype: `{"Customer": [field_dict]}`
  - Multiple doctypes: `{("Customer", "Supplier"): [field_dict]}`
- `ignore_validate`: Skip validation (default: False)
- `update`: Update existing fields (default: True)

**Location**: `frappe/custom/doctype/custom_field/custom_field.py:314-380`

#### `get_fields_label(doctype=None)`

Returns list of field labels for a doctype (for UI dropdown).

**Location**: `frappe/custom/doctype/custom_field/custom_field.py:269-282`

#### `rename_fieldname(custom_field: str, fieldname: str)`

Renames a custom field's fieldname.

**Location**: `frappe/custom/doctype/custom_field/custom_field.py:396-425`

**Process**:
1. Validates system-generated fields cannot be renamed (line 407-408)
2. Checks column doesn't exist (line 409-410)
3. Renames database column if exists (line 415-416)
4. Updates fieldname in Custom Field document (line 420)
5. Updates references (line 421)

**Reference**: `frappe/custom/doctype/custom_field/custom_field.py:396-425`

### Metadata Methods

#### `Meta.add_custom_fields()`

Merges custom fields into DocType metadata.

**Location**: `frappe/model/meta.py:399-415`

#### `Meta.get_custom_fields()`

Returns list of custom fields from metadata.

**Location**: `frappe/model/meta.py:363-364`

#### `Meta.sort_fields()`

Sorts fields including custom fields based on insert_after.

**Location**: `frappe/model/meta.py:518-590`

---

## Restrictions & Limitations

### DocType Restrictions

Custom fields **cannot** be added to the following types of DocTypes:

#### 1. Core DocTypes

Core DocTypes are system-level doctypes that cannot be customized. The list includes:

**Location**: `frappe/model/__init__.py:101-120`

```python
core_doctypes_list = (
    "DefaultValue",
    "DocType",
    "DocField",
    "DocPerm",
    "DocType Action",
    "DocType Link",
    "User",
    "Role",
    "Has Role",
    "Page",
    "Module Def",
    "Print Format",
    "Report",
    "Customize Form",
    "Customize Form Field",
    "Property Setter",
    "Custom Field",
    "Client Script",
)
```

**Validation**: `frappe/custom/doctype/custom_field/custom_field.py:273-274`

```python
if doctype in core_doctypes_list:
    return frappe.msgprint(_("Custom Fields cannot be added to core DocTypes."))
```

**UI Filter**: `frappe/custom/doctype/custom_field/custom_field.js:13`

```javascript
["DocType", "name", "not in", frappe.model.core_doctypes_list]
```

#### 2. Single DocTypes

Single DocTypes (`issingle = 1`) store data in the `tabSingles` table and cannot have custom fields.

**UI Filter**: `frappe/custom/doctype/custom_field/custom_field.js:11`

```javascript
["DocType", "issingle", "=", 0]
```

**Validation**: `frappe/custom/doctype/customize_form/customize_form.py:124-125`

```python
if meta.issingle:
    frappe.throw(_("Single DocTypes cannot be customized."))
```

**Note**: Single DocTypes cannot be customized at all, not just via custom fields.

#### 3. Custom DocTypes

Custom fields can only be added to **standard** DocTypes, not custom DocTypes.

**UI Filter**: `frappe/custom/doctype/custom_field/custom_field.js:12`

```javascript
["DocType", "custom", "=", 0]
```

**Validation**: `frappe/custom/doctype/custom_field/custom_field.py:276-277`

```python
if meta.custom:
    return frappe.msgprint(_("Custom Fields can only be added to a standard DocType."))
```

**Also Checked In**: `frappe/custom/doctype/customize_form/customize_form.py:127-128`

```python
if meta.custom:
    frappe.throw(_("Only standard DocTypes are allowed to be customized from Customize Form."))
```

#### 4. Module Restrictions (Non-Administrator Users)

For non-Administrator users, custom fields cannot be added to DocTypes in the "Core" or "Custom" modules.

**UI Filter**: `frappe/custom/doctype/custom_field/custom_field.js:16-17`

```javascript
if (frappe.session.user !== "Administrator") {
    filters.push(["DocType", "module", "not in", ["Core", "Custom"]]);
}
```

**Note**: Administrator users can add custom fields to any standard DocType (except core, single, and custom doctypes).

#### 5. Domain Restrictions

DocTypes with `restrict_to_domain` are filtered based on active domains.

**UI Filter**: `frappe/custom/doctype/custom_field/custom_field.js:14`

```javascript
["DocType", "restrict_to_domain", "in", frappe.boot.active_domains]
```

### Restricted Fieldnames

The following fieldnames cannot be used (automatically suffixed with "1"):

**Location**: `frappe/custom/doctype/custom_field/custom_field.py:127-138`

```python
restricted = (
    "name", "parent", "creation", "modified", "modified_by",
    "parentfield", "parenttype", "file_list", "flags", "docstatus"
)
```

### Fieldtype Changes

Fieldtype changes are restricted for non-virtual fields:

**Check**: `frappe/custom/doctype/custom_field/custom_field.py:186-194`

```python
if (not self.is_virtual and 
    old_fieldtype != self.fieldtype and
    not CustomizeForm.allow_fieldtype_change(old_fieldtype, self.fieldtype)):
    frappe.throw(_("Fieldtype cannot be changed from {0} to {1}"))
```

### Summary of DocType Restrictions

| Restriction | Condition | Location |
|------------|-----------|----------|
| Core DocTypes | `doctype in core_doctypes_list` | `frappe/model/__init__.py:101-120` |
| Single DocTypes | `issingle = 1` | `frappe/custom/doctype/custom_field/custom_field.js:11` |
| Custom DocTypes | `custom = 1` | `frappe/custom/doctype/custom_field/custom_field.js:12` |
| Core/Custom Modules | Non-Administrator users | `frappe/custom/doctype/custom_field/custom_field.js:16-17` |
| Domain Restricted | Based on active domains | `frappe/custom/doctype/custom_field/custom_field.js:14` |

---

## Developer Mode Behavior

Developer mode (`frappe.conf.developer_mode = 1`) affects custom field functionality in several ways:

### 1. Export Customizations

Exporting custom fields to JSON files is **only allowed in developer mode**.

**Function**: `export_customizations()`  
**Location**: `frappe/modules/utils.py:54-97`

**Restriction**: `frappe/modules/utils.py:64-65`

```python
if not frappe.conf.developer_mode:
    frappe.throw(_("Only allowed to export customizations in developer mode"))
```

**What It Does**:
- Exports custom fields, property setters, and custom permissions to `{app}/{module}/custom/{doctype}.json`
- Recursively exports customizations for child table doctypes
- Sets `sync_on_migrate` flag for automatic syncing during migrations

**Usage**: Called from UI when exporting customizations for a DocType.

### 2. Auto-Export on Standard Document Creation

When creating standard documents (not custom) in developer mode, they are automatically exported to files.

**Location**: `frappe/modules/utils.py:32-40`

```python
if not frappe.flags.in_import and is_standard and frappe.conf.developer_mode:
    from frappe.modules.export_file import export_to_files
    export_to_files(record_list=[[doc.doctype, doc.name]], record_module=module, create_init=is_standard)
```

**Note**: This applies to standard DocTypes, not specifically to custom fields, but affects the overall customization workflow.

### 3. Developer Mode in Frontend

Developer mode status is available in the frontend via `frappe.boot.developer_mode`:

**Usage Examples**:
- `frappe/public/js/frappe/utils/utils.js:1685` - Conditional UI behavior
- `frappe/public/js/frappe/views/reports/query_report.js:230` - Setting standard flags
- `frappe/public/js/frappe/views/pageview.js:23` - Caching behavior

### 4. Impact on Custom Field Workflow

**With Developer Mode Enabled**:
- ✅ Can export custom fields to JSON files
- ✅ Custom fields can be synced from JSON files during migrations
- ✅ Standard documents auto-exported to files
- ✅ Better integration with version control

**Without Developer Mode**:
- ❌ Cannot export custom fields to JSON files
- ✅ Can still create custom fields via UI or API
- ✅ Custom fields still work normally
- ✅ Can still import from existing JSON files (via sync)

### Setting Developer Mode

Developer mode is set in `site_config.json`:

```json
{
    "developer_mode": 1
}
```

Or via environment variable or command line flag during bench setup.

---

## Best Practices

1. **Use Custom Apps**: Define custom fields in JSON files within custom app modules for version control and deployment
2. **Naming Convention**: Fieldnames are auto-prefixed with `custom_` - don't manually add this prefix
3. **System Generated Flag**: Set `is_system_generated: True` for programmatically created fields
4. **Virtual Fields**: Use `is_virtual: 1` for computed fields that don't need database storage
5. **Positioning**: Always specify `insert_after` for predictable field ordering
6. **Validation**: Don't skip validation unless necessary (e.g., during migrations)
7. **Developer Mode**: Enable developer mode when developing custom apps to export customizations
8. **Sync on Migrate**: Set `sync_on_migrate: true` in custom JSON files for automatic syncing

---

## Testing

Test cases are available in:

**File**: `frappe/custom/doctype/custom_field/test_custom_field.py`

**Test Cases**:
- `test_create_custom_fields()` - Tests bulk creation
- `test_custom_field_sorting()` - Tests field ordering
- `test_custom_section_and_column_breaks_ordering()` - Tests break positioning
- `test_custom_field_renaming()` - Tests fieldname renaming

**Reference**: `frappe/custom/doctype/custom_field/test_custom_field.py`

---

## Summary

Custom fields in Frappe provide a powerful mechanism to extend standard DocTypes:

1. **Storage**: Stored in `tabCustom Field` table, separate from DocType JSON
2. **Loading**: Automatically merged into metadata via `Meta.add_custom_fields()`
3. **Schema**: Database columns created via `frappe.db.updatedb()`
4. **Creation**: Via UI, Python API, or custom app JSON files
5. **Ordering**: Controlled by `insert_after` property
6. **Apps**: Can be exported/imported via custom app modules

This architecture allows customization while maintaining upgradability of standard DocTypes.

# DocType Customization in Frappe - Comprehensive Documentation

## Table of Contents
1. [Overview](#overview)
2. [Core Concepts](#core-concepts)
3. [Customization Mechanisms](#customization-mechanisms)
4. [How Customizations Work](#how-customizations-work)
5. [Creating Customizations](#creating-customizations)
6. [Storage and Application](#storage-and-application)
7. [Export and Sync](#export-and-sync)
8. [Implementation Details](#implementation-details)
9. [Restrictions and Limitations](#restrictions-and-limitations)
10. [Developer Mode Behavior](#developer-mode-behavior)

---

## Overview

DocType customization in Frappe allows you to modify standard DocTypes without directly editing their JSON files. This is achieved through two primary mechanisms:

1. **Property Setters** - Override properties of existing fields and DocType-level settings
2. **Custom Fields** - Add new fields to existing DocTypes

The customization system ensures that:
- Standard DocType JSON files remain untouched
- Customizations persist across updates
- Customizations can be exported and synced via fixtures
- Customizations are applied dynamically when metadata is loaded

---

## Core Concepts

### 1. Customize Form (UI Layer)

**File**: `frappe/custom/doctype/customize_form/customize_form.py`

The `CustomizeForm` DocType provides a user-friendly interface for customizing DocTypes. It acts as a wrapper around Property Setters and Custom Fields.

**Key Methods**:
- `fetch_to_customize()` (lines 97-115): Loads existing DocType metadata into the customize form
- `save_customization()` (lines 224-262): Saves customizations by creating/updating Property Setters and Custom Fields
- `set_property_setters()` (lines 264-279): Creates Property Setter records for changed properties
- `update_custom_fields()` (lines 457-468): Creates or updates Custom Field records

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:29-835`

### 2. Property Setter

**File**: `frappe/custom/doctype/property_setter/property_setter.py`

Property Setters override standard properties of DocTypes, DocFields, DocType Links, DocType Actions, and DocType States without modifying the original JSON.

**Key Fields**:
- `doc_type`: The DocType being customized
- `doctype_or_field`: What is being customized (`DocType`, `DocField`, `DocType Link`, `DocType Action`, `DocType State`)
- `field_name`: Field name (for DocField)
- `row_name`: Row name (for DocType Link/Action/State)
- `property`: Property name to override
- `property_type`: Data type of the property
- `value`: New value for the property

**Key Functions**:
- `make_property_setter()` (lines 73-99): Creates a new Property Setter record
- `delete_property_setter()` (lines 102-115): Deletes Property Setter records

**Reference**: `frappe/custom/doctype/property_setter/property_setter.py:11-115`

### 3. Custom Field

**File**: `frappe/custom/doctype/custom_field/custom_field.py`

Custom Fields add new fields to existing DocTypes. They are stored separately and merged with standard fields when metadata is loaded.

**Key Fields**:
- `dt`: DocType name
- `fieldname`: Field name (auto-prefixed with `custom_` if not provided)
- `fieldtype`: Type of field
- `insert_after`: Position where field should be inserted
- `is_system_generated`: Flag for system-generated fields

**Key Functions**:
- `create_custom_field()` (lines 293-311): Creates a single Custom Field
- `create_custom_fields()` (lines 314-380): Creates/updates multiple Custom Fields

**Reference**: `frappe/custom/doctype/custom_field/custom_field.py:16-443`

---

## Customization Mechanisms

### Mechanism 1: Property Setters

Property Setters modify existing properties without changing the source JSON. They can override:

1. **DocType Properties**: Properties at the DocType level
   - Examples: `search_fields`, `title_field`, `sort_field`, `allow_copy`, `track_changes`, etc.
   - **Reference**: `frappe/custom/doctype/customize_form/customize_form.py:718-750` (doctype_properties dictionary)

2. **DocField Properties**: Properties of existing fields
   - Examples: `label`, `fieldtype`, `options`, `reqd`, `hidden`, `read_only`, `in_list_view`, etc.
   - **Reference**: `frappe/custom/doctype/customize_form/customize_form.py:752-802` (docfield_properties dictionary)

3. **DocType Link/Action/State Properties**: Properties of links, actions, and states
   - **Reference**: `frappe/custom/doctype/customize_form/customize_form.py:804-819`

### Mechanism 2: Custom Fields

Custom Fields add entirely new fields to DocTypes. They:
- Are stored in the `Custom Field` DocType
- Are automatically prefixed with `custom_` if fieldname is not provided
- Can be positioned using `insert_after`
- Are merged with standard fields when metadata is loaded

---

## How Customizations Work

### Metadata Loading Process

When a DocType's metadata is loaded, customizations are applied in the following order:

**File**: `frappe/model/meta.py`

1. **Load Standard DocType** (line 152-159): Loads the DocType from database or JSON file
2. **Process Metadata** (line 161-175): Applies customizations
   - `add_custom_fields()` (line 168, implementation at lines 399-415)
   - `apply_property_setters()` (line 169, implementation at lines 417-462)
   - `add_custom_links_and_actions()` (line 174, implementation at lines 464-489)

### Step-by-Step Application

#### 1. Adding Custom Fields

**Method**: `Meta.add_custom_fields()`  
**File**: `frappe/model/meta.py:399-415`

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
        update={"is_custom_field": 1},
    )
    
    if not custom_fields:
        return
    
    self.extend("fields", custom_fields)
```

**Process**:
1. Queries all Custom Fields for the DocType
2. Marks them with `is_custom_field: 1`
3. Extends the fields list with custom fields
4. Fields are ordered by `idx` (set via `insert_after`)

**Reference**: `frappe/model/meta.py:399-415`

#### 2. Applying Property Setters

**Method**: `Meta.apply_property_setters()`  
**File**: `frappe/model/meta.py:417-462`

```python
def apply_property_setters(self):
    property_setters = frappe.db.get_values(
        "Property Setter",
        filters={"doc_type": self.name},
        fieldname="*",
        as_dict=True,
    )
    
    for ps in property_setters:
        if ps.doctype_or_field == "DocType":
            self.set(ps.property, cast(ps.property_type, ps.value))
        elif ps.doctype_or_field == "DocField":
            for d in self.fields:
                if d.fieldname == ps.field_name:
                    d.set(ps.property, cast(ps.property_type, ps.value))
                    break
        # ... similar for DocType Link, Action, State
```

**Process**:
1. Queries all Property Setters for the DocType
2. Applies them based on `doctype_or_field`:
   - `DocType`: Sets properties on the DocType itself
   - `DocField`: Finds the field and sets its property
   - `DocType Link/Action/State`: Finds the row and sets its property
3. Uses type casting based on `property_type`

**Reference**: `frappe/model/meta.py:417-462`

#### 3. Adding Custom Links and Actions

**Method**: `Meta.add_custom_links_and_actions()`  
**File**: `frappe/model/meta.py:464-489`

```python
def add_custom_links_and_actions(self):
    for doctype, fieldname in (
        ("DocType Link", "links"),
        ("DocType Action", "actions"),
        ("DocType State", "states"),
    ):
        for d in frappe.get_all(
            doctype, fields="*", filters=dict(parent=self.name, custom=1), ignore_ddl=True
        ):
            self.append(fieldname, d)
        
        # Apply ordering if specified
        order = json.loads(self.get(f"{fieldname}_order") or "[]")
        if order:
            # Reorder based on saved order
```

**Process**:
1. Queries custom DocType Links, Actions, and States (where `custom=1`)
2. Appends them to the respective lists
3. Applies ordering if `{fieldname}_order` property setter exists

**Reference**: `frappe/model/meta.py:464-489`

---

## Creating Customizations

### Method 1: Via Customize Form UI

**File**: `frappe/custom/doctype/customize_form/customize_form.js`

1. Navigate to Customize Form (`/app/customize-form`)
2. Select a DocType (line 54-75)
3. Modify fields and properties
4. Click "Update" button (line 438-441)
5. Calls `save_customization()` method

**Flow**:
```
User selects DocType
  → fetch_to_customize() loads metadata
  → User modifies properties
  → save_customization() is called
    → update_custom_fields() creates/updates Custom Fields
    → set_property_setters() creates Property Setters
    → set_name_translation() updates translations
```

**Reference**: `frappe/custom/doctype/customize_form/customize_form.js:406-422`

### Method 2: Via Database/API

#### Creating Custom Fields Programmatically

**Function**: `create_custom_field()`  
**File**: `frappe/custom/doctype/custom_field/custom_field.py:293-311`

```python
from frappe.custom.doctype.custom_field.custom_field import create_custom_field

create_custom_field(
    "Sales Invoice",
    {
        "fieldname": "custom_notes",
        "label": "Notes",
        "fieldtype": "Text",
        "insert_after": "customer",
    }
)
```

**Reference**: `frappe/custom/doctype/custom_field/custom_field.py:293-311`

#### Creating Property Setters Programmatically

**Function**: `make_property_setter()`  
**File**: `frappe/custom/doctype/property_setter/property_setter.py:73-99`

```python
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

# For DocType property
make_property_setter(
    doctype="Sales Invoice",
    fieldname=None,
    property="allow_copy",
    value="1",
    property_type="Check",
    for_doctype=True
)

# For DocField property
make_property_setter(
    doctype="Sales Invoice",
    fieldname="customer",
    property="reqd",
    value="1",
    property_type="Check"
)
```

**Reference**: `frappe/custom/doctype/property_setter/property_setter.py:73-99`

**Also available as**: `frappe.make_property_setter()`  
**Reference**: `frappe/__init__.py:1507`

### Method 3: Via Custom App Fixtures

Customizations can be exported and included in custom apps as fixtures.

#### Export Customizations

**Function**: `export_customizations()`  
**File**: `frappe/modules/utils.py:55-97`

```python
from frappe.modules.utils import export_customizations

export_customizations(
    module="Custom",
    doctype="Sales Invoice",
    sync_on_migrate=True,
    with_permissions=False
)
```

This creates a JSON file at: `{app}/{module}/custom/{doctype}.json`

**Reference**: `frappe/modules/utils.py:55-97`

#### Fixture File Structure

**Location**: `{app}/{module}/custom/{doctype}.json`

**Structure**:
```json
{
    "doctype": "Sales Invoice",
    "sync_on_migrate": true,
    "custom_fields": [
        {
            "dt": "Sales Invoice",
            "fieldname": "custom_notes",
            "label": "Notes",
            "fieldtype": "Text",
            "insert_after": "customer",
            ...
        }
    ],
    "property_setters": [
        {
            "doc_type": "Sales Invoice",
            "doctype_or_field": "DocField",
            "field_name": "customer",
            "property": "reqd",
            "property_type": "Check",
            "value": "1"
        }
    ],
    "links": [...],
    "custom_perms": [...]
}
```

**Reference**: `frappe/modules/utils.py:55-97`

#### Sync Customizations

**Function**: `sync_customizations()`  
**File**: `frappe/modules/utils.py:100-119`

Customizations are automatically synced during:
- `bench migrate` (line 154 in `frappe/migrate.py`)
- App installation (line 329 in `frappe/installer.py`)

**Process**:
1. Scans all apps for `{module}/custom/*.json` files
2. If `sync_on_migrate: true`, syncs the customizations
3. Calls `sync_customizations_for_doctype()` for each file

**Reference**: `frappe/modules/utils.py:100-194`

**Sync Implementation**: `sync_customizations_for_doctype()`  
**File**: `frappe/modules/utils.py:122-194`

```python
def sync_customizations_for_doctype(data: dict, folder: str, filename: str = ""):
    doctype = data["doctype"]
    
    # Sync Custom Fields
    if data["custom_fields"]:
        sync("custom_fields", "Custom Field", "dt")
    
    # Sync Property Setters
    if data["property_setters"]:
        sync("property_setters", "Property Setter", "doc_type")
    
    # Sync Custom Permissions
    if data.get("custom_perms"):
        sync("custom_perms", "Custom DocPerm", "parent")
```

**Reference**: `frappe/modules/utils.py:122-194`

---

## Storage and Application

### Database Tables

1. **Custom Field Table**: `tabCustom Field`
   - Stores all custom fields
   - Key fields: `dt`, `fieldname`, `fieldtype`, `insert_after`, `idx`
   - **Reference**: `frappe/custom/doctype/custom_field/custom_field.json`

2. **Property Setter Table**: `tabProperty Setter`
   - Stores all property overrides
   - Key fields: `doc_type`, `doctype_or_field`, `field_name`, `property`, `value`
   - **Reference**: `frappe/custom/doctype/property_setter/property_setter.json`

3. **DocType Link/Action/State Tables**: `tabDocType Link`, `tabDocType Action`, `tabDocType State`
   - Stores custom links, actions, and states
   - Marked with `custom=1` flag
   - **Reference**: `frappe/model/meta.py:464-489`

### Metadata Cache

Metadata is cached to improve performance:
- Cache key: `doctype_meta::{doctype}`
- Cleared when customizations are updated
- **Reference**: `frappe/model/meta.py:68-88`

**Cache Clearing**:
- When Custom Field is saved: `frappe/custom/doctype/custom_field/custom_field.py:213`
- When Property Setter is saved: `frappe/custom/doctype/property_setter/property_setter.py:44`
- When Customize Form saves: `frappe/custom/doctype/customize_form/customize_form.py:254`

---

## Export and Sync

### Export Process

**UI Export**:
1. Open Customize Form
2. Select DocType
3. Click "Export Customizations" (developer mode only)
4. Select module and options
5. File is created at `{module}/custom/{doctype}.json`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.js:239-285`

**Programmatic Export**:
```python
from frappe.modules.utils import export_customizations

export_customizations(
    module="Custom",
    doctype="Sales Invoice",
    sync_on_migrate=True,
    with_permissions=False
)
```

**Reference**: `frappe/modules/utils.py:55-97`

### Sync Process

**Automatic Sync** (during migrate):
1. `bench migrate` calls `sync_customizations()`
2. Scans all apps for `custom/*.json` files
3. Syncs files with `sync_on_migrate: true`
4. Creates/updates Custom Fields and Property Setters in database

**Reference**: `frappe/migrate.py:154`

**Manual Sync**:
```python
from frappe.modules.utils import sync_customizations

sync_customizations(app="my_app")
```

**Reference**: `frappe/modules/utils.py:100-119`

### Sync Behavior

**Custom Fields**:
- If field doesn't exist: Creates new Custom Field
- If field exists: Updates existing Custom Field
- Uses `db_update()` to avoid triggering validation hooks

**Property Setters**:
- Property Setters implement their own deduplication
- Uses `insert()` which handles duplicates via autoname
- Sets `validate_fields_for_doctype=False` flag

**Reference**: `frappe/modules/utils.py:129-172`

---

## Implementation Details

### Field Ordering

Field order is maintained via:
1. `idx` field in Custom Field (set based on `insert_after`)
2. `field_order` Property Setter (JSON array of fieldnames)

**Setting Field Order**:
- **Method**: `set_property_setter_for_field_order()`  
- **File**: `frappe/custom/doctype/customize_form/customize_form.py:281-305`

```python
def set_property_setter_for_field_order(self, meta):
    new_order = [df.fieldname for df in self.fields]
    frappe.make_property_setter({
        "doctype": self.doc_type,
        "doctype_or_field": "DocType",
        "property": "field_order",
        "value": json.dumps(new_order),
    })
```

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:281-305`

### Validation

**Field Type Changes**:
- Only certain field type changes are allowed
- Defined in `ALLOWED_FIELDTYPE_CHANGE`
- **Reference**: `frappe/custom/doctype/customize_form/customize_form.py:822-832`

**Restrictions**:
- Cannot customize core DocTypes
- Cannot customize Single DocTypes
- Cannot customize custom DocTypes (only standard)
- Cannot delete standard fields (can hide them)
- Cannot change certain properties (e.g., `reqd` on standard fields)

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:117-128`

### Custom Field Naming

**Auto-naming**:
- If `fieldname` not provided, generated from `label`
- Prefixed with `custom_` if not already prefixed
- Lowercased and sanitized

**Method**: `set_fieldname()`  
**File**: `frappe/custom/doctype/custom_field/custom_field.py:126-157`

**Reference**: `frappe/custom/doctype/custom_field/custom_field.py:126-157`

### Property Setter Naming

**Auto-naming**:
- Format: `{doctype}-{field}-{property}`
- Example: `Sales Invoice-customer-reqd`

**Method**: `autoname()`  
**File**: `frappe/custom/doctype/property_setter/property_setter.py:34-37`

**Reference**: `frappe/custom/doctype/property_setter/property_setter.py:34-37`

### Database Schema Updates

When Custom Fields are added/updated:
- `frappe.db.updatedb()` is called to update database schema
- Adds/alters columns in the database table
- **Reference**: `frappe/custom/doctype/custom_field/custom_field.py:214`

### Translation Support

Customizations support translations:
- Custom field labels can be translated
- DocType labels can be translated via Property Setter
- Translations stored in `Translation` DocType

**Method**: `set_name_translation()`  
**File**: `frappe/custom/doctype/customize_form/customize_form.py:187-209`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:187-209`

### Custom Links and Actions Ordering

Ordering is maintained via Property Setters:
- `links_order`: JSON array of link names
- `actions_order`: JSON array of action names
- `states_order`: JSON array of state names

**Method**: `update_order_property_setter()`  
**File**: `frappe/custom/doctype/customize_form/customize_form.py:434-446`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:434-446`

---

## Restrictions and Limitations

### DocType-Level Restrictions

#### 1. Core DocTypes Cannot Be Customized

**Core DocTypes** are system-level DocTypes that cannot be customized. Attempting to customize them will throw an error: `"Core DocTypes cannot be customized."`

**List of Core DocTypes**:
- `DefaultValue`
- `DocType`
- `DocField`
- `DocPerm`
- `DocType Action`
- `DocType Link`
- `User`
- `Role`
- `Has Role`
- `Page`
- `Module Def`
- `Print Format`
- `Report`
- `Customize Form`
- `Customize Form Field`
- `Property Setter`
- `Custom Field`
- `Client Script`

**Reference**: `frappe/model/__init__.py:101-120`

**Validation**:
- **Customize Form**: `frappe/custom/doctype/customize_form/customize_form.py:121-122`
- **Custom Field**: `frappe/custom/doctype/custom_field/custom_field.py:273-274`
- **UI Filter**: `frappe/custom/doctype/customize_form/customize_form.js:22`

#### 2. Single DocTypes Cannot Be Customized

Single DocTypes (where `issingle=1`) cannot be customized. They store data in the `tabSingles` table instead of a dedicated table.

**Error**: `"Single DocTypes cannot be customized."`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:124-125`

**UI Filter**: `frappe/custom/doctype/customize_form/customize_form.js:20`

#### 3. Only Standard DocTypes Can Be Customized

Custom DocTypes (where `custom=1`) cannot be customized via Customize Form. Only standard DocTypes (where `custom=0`) can be customized.

**Error**: `"Only standard DocTypes are allowed to be customized from Customize Form."`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:127-128`

**Note**: Custom DocTypes can still have Custom Fields added programmatically, but not through the Customize Form UI.

**UI Filter**: `frappe/custom/doctype/customize_form/customize_form.js:21`

#### 4. Domain Restrictions

DocTypes can be restricted to specific domains. The Customize Form UI filters DocTypes based on active domains.

**UI Filter**: `frappe/custom/doctype/customize_form/customize_form.js:23`

```javascript
["DocType", "restrict_to_domain", "in", frappe.boot.active_domains]
```

Only DocTypes that match the active domains (or have no domain restriction) are shown in the Customize Form.

### Field-Level Restrictions

#### 1. Cannot Enable "Allow on Submit" for Standard Fields

Standard fields cannot have "Allow on Submit" enabled if it wasn't already enabled in the original DocType.

**Error**: `"Not allowed to enable Allow on Submit for standard fields"`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:336-343`

#### 2. Cannot Disable "Mandatory" for Standard Fields

If a standard field is marked as mandatory (`reqd=1`), you cannot disable this requirement.

**Error**: `"Not allowed to disable Mandatory for standard fields"`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:345-353`

#### 3. Cannot Set "In List View" for Certain Field Types

Fields of type `Section Break`, `Column Break`, `Tab Break`, `HTML`, `Table`, `Table MultiSelect`, `Button`, `Image`, `Fold`, or `Heading` cannot be shown in list view (except `Attach Image`).

**Error**: `"'In List View' not allowed for type {fieldtype} in row {idx}"`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:355-364`

**Field Types**: Defined in `frappe/model/__init__.py:53-64` (`no_value_fields`)

#### 4. Cannot Unset "Read Only" for Read-Only Fields

If a standard field has `read_only=1` set in the DocType JSON, you cannot make it editable.

**Error**: `"You cannot unset 'Read Only' for field {label}"`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:376-386`

#### 5. Cannot Set "Options" for Certain Field Types

Only fields of type `Read Only`, `HTML`, or `Data` can have their `options` property changed.

**Error**: `"You can't set 'Options' for field {label}"`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:388-390`

**Allowed Types**: Defined in `frappe/custom/doctype/customize_form/customize_form.py:834` (`ALLOWED_OPTIONS_CHANGE`)

#### 6. Cannot Set "Translatable" for Unsupported Field Types

Only certain field types support translation. Attempting to set `translatable=1` for unsupported types will fail.

**Error**: `"You can't set 'Translatable' for field {label}"`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:392-394`

**Validation**: `frappe/model/docfield.py` - `supports_translation()` function

#### 7. Field Type Changes Are Restricted

Field types can only be changed within allowed groups. Attempting to change from one type to another outside the allowed groups will fail.

**Error**: `"Fieldtype cannot be changed from {old} to {new} in row {idx}"`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:569-591`

**Allowed Changes**: Defined in `frappe/custom/doctype/customize_form/customize_form.py:822-832` (`ALLOWED_FIELDTYPE_CHANGE`)

**Allowed Groups**:
- `("Currency", "Float", "Percent")`
- `("Small Text", "Data")`
- `("Text", "Data")`
- `("Text", "Text Editor", "Code", "Signature", "HTML Editor")`
- `("Data", "Select")`
- `("Text", "Small Text", "Long Text")`
- `("Text", "Data", "Barcode")`
- `("Code", "Geolocation")`
- `("Table", "Table MultiSelect")`

**Note**: Virtual fields (`is_virtual=1`) can have their field type changed without restriction.

**Reference**: `frappe/custom/doctype/customize_form/customize_form.py:570-571`

#### 8. Cannot Delete Standard Fields

Standard fields cannot be deleted. They can only be hidden.

**Error**: `"Cannot delete standard field {label}. You can hide it instead."`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.js:318-324`

#### 9. Cannot Delete System Generated Fields

System-generated fields cannot be deleted, even if they are custom fields.

**Error**: `"Cannot delete system generated field {label}. You can hide it instead."`

**Reference**: `frappe/custom/doctype/customize_form/customize_form.js:309-316`

### Standard Links, Actions, and States Restrictions

#### Cannot Delete Standard Links/Actions/States

Standard DocType Links, Actions, and States cannot be deleted. They can only be hidden.

**Errors**:
- `"Cannot delete standard link. You can hide it if you want"`
- `"Cannot delete standard action. You can hide it if you want"`
- `"Cannot delete standard document state."`

**Reference**: 
- Links: `frappe/custom/doctype/customize_form/customize_form.js:342-349`
- Actions: `frappe/custom/doctype/customize_form/customize_form.js:364-371`
- States: `frappe/custom/doctype/customize_form/customize_form.js:386-393`

---

## Developer Mode Behavior

### What is Developer Mode?

Developer mode (`developer_mode=1` in `site_config.json`) enables additional features for developers, including exporting customizations and auto-exporting standard documents.

### Developer Mode Restrictions

#### 1. Export Customizations Requires Developer Mode

The `export_customizations()` function can only be called when developer mode is enabled.

**Error**: `"Only allowed to export customizations in developer mode"`

**Reference**: `frappe/modules/utils.py:64-65`

**UI**: The "Export Customizations" button only appears in developer mode.

**Reference**: `frappe/custom/doctype/customize_form/customize_form.js:240`

```javascript
if (frappe.boot.developer_mode) {
    frm.add_custom_button(__("Export Customizations"), ...)
}
```

#### 2. Auto-Export Standard Documents Requires Developer Mode

When `export_module_json()` is called for standard documents, it only exports to files if developer mode is enabled.

**Reference**: `frappe/modules/utils.py:32`

```python
if not frappe.flags.in_import and is_standard and frappe.conf.developer_mode:
    export_to_files(...)
```

This means that when you create or modify standard documents (like Print Formats, Reports, etc.) in developer mode, they are automatically exported to JSON files in the app directory.

### Developer Mode Benefits

1. **Export Customizations**: Export customizations to JSON files for version control
2. **Auto-Export**: Standard documents are automatically exported to files
3. **Development Workflow**: Easier to develop and maintain customizations

### Enabling Developer Mode

Add to `site_config.json`:
```json
{
    "developer_mode": 1
}
```

Or set via environment variable:
```bash
export FRAPPE_DEVELOPER_MODE=1
```

**Note**: Developer mode should **NOT** be enabled in production environments as it can expose sensitive information and allow unintended modifications.

---

## Summary

DocType customization in Frappe works through:

1. **Property Setters**: Override properties without modifying JSON
2. **Custom Fields**: Add new fields stored separately
3. **Metadata Merging**: Customizations are applied when metadata is loaded
4. **Export/Sync**: Customizations can be exported and synced via fixtures
5. **Database Storage**: All customizations stored in database tables
6. **Dynamic Application**: Customizations applied at runtime, not at install time

This architecture ensures:
- ✅ Standard DocTypes remain untouched
- ✅ Customizations persist across updates
- ✅ Customizations can be version controlled
- ✅ Customizations can be shared via custom apps
- ✅ No JSON file modifications required

### Restrictions Summary

**DocType Restrictions**:
- ❌ Core DocTypes (19 types) cannot be customized
- ❌ Single DocTypes cannot be customized
- ❌ Custom DocTypes cannot be customized via UI (only standard)
- ⚠️ Domain-restricted DocTypes filtered by active domains

**Field Restrictions**:
- ❌ Cannot enable "Allow on Submit" for standard fields
- ❌ Cannot disable "Mandatory" for standard fields
- ❌ Cannot set "In List View" for no-value field types
- ❌ Cannot unset "Read Only" for read-only fields
- ❌ Cannot set "Options" for unsupported field types
- ❌ Cannot set "Translatable" for unsupported field types
- ❌ Field type changes restricted to allowed groups
- ❌ Cannot delete standard/system-generated fields

**Developer Mode**:
- ✅ Export customizations requires developer mode
- ✅ Auto-export standard documents requires developer mode
- ⚠️ Should not be enabled in production

---

## Key File References

| Component | File Path | Key Lines |
|-----------|-----------|-----------|
| Customize Form Controller | `frappe/custom/doctype/customize_form/customize_form.py` | 29-835 |
| Customize Form UI | `frappe/custom/doctype/customize_form/customize_form.js` | 1-514 |
| Property Setter | `frappe/custom/doctype/property_setter/property_setter.py` | 11-115 |
| Custom Field | `frappe/custom/doctype/custom_field/custom_field.py` | 16-443 |
| Metadata Loading | `frappe/model/meta.py` | 125-489 |
| Export Customizations | `frappe/modules/utils.py` | 55-97 |
| Sync Customizations | `frappe/modules/utils.py` | 100-194 |
| Migration Hook | `frappe/migrate.py` | 154 |

---

## Additional Resources

- **Customization Extractor** (for translations): `frappe/gettext/extractors/customization.py`
- **Customize Form Field** (child table): `frappe/custom/doctype/customize_form_field/customize_form_field.py`
- **Reset Customization**: `frappe/custom/doctype/customize_form/customize_form.py:678-700`

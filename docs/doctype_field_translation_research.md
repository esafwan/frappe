# Frappe DocType Field Architecture & Current Translation Capabilities

## Current Architecture: DocType Fields & Translation in Frappe

### 1. Knowledge bootstrap from the external skill package

I first attempted to fetch `https://github.com/esafwan/Frappe_Claude_Skill_Package` directly with `git clone`, but outbound GitHub access from the shell was blocked in this environment (`CONNECT tunnel failed, response 403`). I therefore used GitHub's raw web endpoints to review the relevant skill package material before inspecting Frappe source.

The key skill package observations were:

- `INDEX.md` identifies `frappe-syntax-doctypes` as the DocType-definition skill and describes it as the reference for creating/modifying DocType JSON, choosing field types, child tables, naming rules, and tree structures.
- The same index maps translation work to `frappe-core-translation`, which is explicitly positioned around `_()`, `__()`, CSV/PO files, and extraction rules.
- The translation skill content reinforces that the built-in translation workflow is string/i18n oriented; it does not describe runtime substitution of database field values for arbitrary document content.

### 2. How DocTypes and fields are defined

Frappe stores the structural definition of a standard DocType in a JSON file and mirrors that definition into metadata tables at runtime.

#### Standard DocType structure

A DocType JSON file contains high-level DocType properties plus a `fields` table whose rows are `DocField` records. The `DocType` schema itself declares its `fields` property as a `Table` with `options: "DocField"`, which means every DocType definition is composed from child `DocField` rows.

Relevant consequences:

- Standard DocType definitions are file-backed in app code.
- On save/export in developer mode, Frappe writes the DocType record back to `[module]/doctype/[name]/[name].json`.
- Controller/template boilerplate can also be scaffolded during export.

#### Field metadata model

`DocField` is the canonical schema for field definitions. It includes, among many others, these important properties:

- `fieldname`
- `label`
- `fieldtype`
- `options`
- `default`
- `fetch_from`
- `in_list_view`
- `in_global_search`
- `translatable`

The `translatable` property exists today, but only on supported field types. Frappe explicitly restricts it to `Data`, `Select`, `Text`, `Small Text`, and `Text Editor` through `supports_translation(fieldtype)`.

#### Customizations and database storage

There are two distinct persistence paths:

1. **Standard fields** are defined in DocType JSON and stored in metadata tables as `DocField` rows (`tabDocField`) attached to the parent `DocType` (`tabDocType`).
2. **Runtime customization fields** are stored separately as `Custom Field` rows (`tabCustom Field`). `Custom Field` mirrors many `DocField` properties, including `label`, `fieldtype`, `options`, and `translatable`.

This means the field schema is metadata-driven, but the actual user-entered values for document records remain stored in the underlying DocType table (`tabItem`, `tabCustomer`, etc.) or in `tabSingles` for single doctypes.

### 3. What field metadata exists for localization today

Existing metadata relevant to translation/localization falls into three buckets:

#### A. Structural metadata

- `label`
- `description`
- `options` for select fields
- DocType-level flags such as `translate_link_fields`

These are metadata or display settings, not multilingual value stores.

#### B. Field-level `translatable`

The `translatable` checkbox exists on both `DocField` and `Custom Field`. However, in core Frappe, this property is only consumed for **translation of displayed/exported values as strings**, not as a mechanism for storing per-document translated content.

The clearest core use is `frappe.desk.reportview`, where exported report rows call `_()` on field values when the field is marked `translatable`. That behavior assumes the field value itself is a translation key present in the translation dictionary. It does **not** load a translated variant from a per-document translation store.

#### C. Language context

Frappe resolves the active request language through `frappe.translate.get_language()` using this priority:

1. `frappe.form_dict._lang`
2. preferred-language cookie (guest/non-authenticated path)
3. `Accept-Language` header
4. logged-in user's language
5. system default language

For authenticated sessions, `frappe.local.lang` is initialized during auth/session bootstrap and then used by translation helpers.

#### D. What the frontend and API actually do with `translatable` today

This is the critical detail for the React-app question. In current Frappe, the existence of `df.translatable = 1` does **not** mean generic data APIs will return translated field values. The property is exposed as metadata, but standard record reads do not automatically act on it.

Current behavior is split across three frontend/API patterns:

1. **Metadata exposure only**
   - DocField metadata synced to the client includes `translatable`, so frontend code can inspect it.
   - This means a Desk page, Vue component, or React app can *see* that a field is marked translatable if it loads DocType meta.
   - However, `frappe.client.get`, `frappe.client.get_value`, `frappe.db.get_doc`, REST `/api/resource`, and normal list reads still return the stored source value.

2. **String-translation UX in Desk**
   - Form controls show a globe button for `df.translatable` fields.
   - That button opens `TranslationManager`, which reads/writes rows in the `Translation` DocType keyed by `source_text`.
   - This is a UI for source-string translation, not document-instance translation. Two records with the same source text still share the same translation key.

3. **Narrow translation-aware rendering paths**
   - Link controls, list formatting for translated link doctypes, and report export can call `__()` / `_()` on returned values.
   - These flows depend on translation dictionaries and `translated_doctype`/`translate_values` style flags.
   - They do not change the underlying API contract for `get_doc`/`get_list`/`get_value`.

Practical consequence for a React app:

- If the React app is calling normal document APIs and expecting `translatable` fields to already be language-resolved, it will not happen automatically.
- Changing only request params on standard `/api/resource` or `frappe.client.get` calls is not enough today, because there is no general-purpose server-side translation overlay for arbitrary field values in those endpoints.
- The frontend can use `translatable` as a hint for custom rendering logic, but it would still need a translation-aware API response shape or a second translation lookup source.

### 4. How standard DocType scaffolding works

DocType scaffolding is tied to saving/exporting standard DocTypes in developer mode.

When a standard DocType is updated, Frappe can:

- export the DocType back to its JSON file,
- generate the controller boilerplate,
- generate test/controller JS templates,
- update Python type annotations for the controller.

This is important for design work because any new translation architecture that wants to feel native should fit this metadata-driven/exportable model instead of bypassing it with ad hoc runtime tables per app unless necessary.

### 5. How documents are fetched today

#### `frappe.get_doc`

`frappe.get_doc()` dispatches to the DocType controller and loads a `Document` instance. For persisted documents, `Document.load_from_db()` performs a raw `SELECT *` on the doctype table (or `frappe.db.get_value(..., fieldname="*")` in some cases), hydrates the `Document`, then loads child tables via `load_children_from_db()`.

Important implications:

- field values are loaded directly from the document table columns,
- there is no built-in translation resolution step between DB load and document hydration,
- after hydration, Frappe may run `onload`, field-level permission filtering, masking, and response serialization.

#### `frappe.get_value`

Top-level `frappe.get_value()` is just an alias to `frappe.db.get_value()`. It reads directly from the database and returns raw stored column values.

The whitelisted client API `frappe.client.get_value()` ultimately calls `get_list(... limit_page_length=1 ...)` for non-single doctypes, so it also returns raw DB values unless custom logic is added above that layer.

#### `frappe.get_list`

Top-level `frappe.get_list()` delegates to `DatabaseQuery.execute(...)`. That path builds and runs SQL against the base doctype table and returns rows. There is no built-in field translation substitution step in that result path.

There is one exception worth calling out: exported report data can optionally translate values for fields flagged `translatable`, but this is report/export formatting behavior, not ORM/runtime document translation.

#### REST API: `/api/resource/`

The REST read paths also rely on the same raw document/query behavior:

- `/api/resource/<doctype>/<name>` in v1 calls `frappe.get_doc()`, then permissions, then returns the doc.
- `/api/v2/document/<doctype>/<name>` does the same and returns `doc.as_dict()`.
- list endpoints use query-builder/database-query paths and return DB-selected fields.

Therefore the REST API inherits the same limitation: it returns stored values, not per-language translated document content.

### 6. Frontend, Desk, and API implications for `translatable` fields

This section answers the practical question: **if a frontend app is not picking up translated values today, should it change the API call, REST route, or params?**

### A. Desk/frontend behavior in core today

#### DocType meta contains the flag

Client-side meta sync loads full DocField definitions into `frappe.meta`, so the browser can inspect `df.translatable`. This is why the frontend knows enough to show a translation affordance, but not enough to resolve translated content automatically.

#### Form controls use `translatable` for translation management UI

`BaseControl.show_translatable_button()` shows the globe button only when all of the following are true:

- the field has `df.translatable`,
- the user can write `Translation`,
- the field has a non-empty value,
- Desk translation UI is available.

That button launches `TranslationManager`, which reads/writes `Translation` rows by `source_text`. In other words, the built-in form UX treats the field value as a string key into the translation dictionary; it does not persist a translation specific to `{doctype, docname, fieldname}`.

#### Link and list formatting have a separate path

Core frontend code also has special handling for link doctypes marked `translated_doctype`. In those cases, the browser uses `frappe.boot.translated_doctypes` and calls `__()` on link titles/display values. This is again dictionary-based display translation, mainly for master data / link-title presentation, not arbitrary per-record field-value substitution.

### B. API behavior in core today

#### Standard reads do not have a `translatable` response mode

The main APIs used by frontend apps are:

- `frappe.client.get` / `frappe.db.get_doc`
- `frappe.client.get_value` / `frappe.db.get_value`
- `frappe.desk.reportview.get_list` / `frappe.db.get_list`
- REST `/api/resource/<doctype>` and `/api/resource/<doctype>/<name>`

None of these endpoints currently accept a general parameter such as:

- `translate_fields=1`
- `resolve_translatable=1`
- `lang=ar` for field-value overlay

that would cause arbitrary `df.translatable` document fields to come back translated.

#### Existing translation-related params are narrow-purpose only

There **is** a `translate_values` parameter in report export and in some autocomplete/link-query flows, but this only controls string translation using translation dictionaries in those narrow flows. It is not a generic REST/data API contract for document retrieval.

### C. What this means for a React app

If the React app is calling standard APIs, there are only three realistic explanations for "not picking it up":

1. the app is receiving meta where `translatable` is visible, but the backend still returns raw source values;
2. the app is using REST/`frappe.client.get`/`frappe.client.get_value`, which have no built-in translated-value mode for arbitrary fields;
3. the app expects `translatable` to behave like a localized content flag, while current core uses it mostly as a source-string translation hint.

### D. Recommended integration direction for frontend consumers

For the proposed multilingual document-data design, the frontend should **not** rely on the current `translatable` flag alone to magically change standard API responses. Instead, the backend contract needs to be explicit.

Recommended options for frontend integration, in order of preference:

#### Option 1 — Keep standard endpoints, change backend behavior behind them

Best fit if transparent behavior is required.

- Keep using the same API shapes (`frappe.client.get`, `frappe.client.get_value`, `frappe.client.get_list`, `/api/resource`).
- Add the translation overlay in the backend service layer so these endpoints already return translated values when the effective request language is not the source language.
- The React app does **not** need a new parameter; it only needs the request language context (`_lang`, session language, or authenticated user preference) to be correct.

This is the cleanest option if the requirement is "users should each see field values in their own language when calling standard APIs."

#### Option 2 — Add an explicit opt-in request parameter during rollout

Best fit for backwards-compatible rollout.

Add a custom API extension such as:

- `GET /api/resource/Item/ITEM-001?_lang=ar&with_translations=1`
- `frappe.client.get({ doctype, name, with_translations: 1 })`
- `frappe.client.get_list({ doctype, fields, with_translations: 1 })`

Behavior:

- when `with_translations` is false/absent, return stored source values;
- when `with_translations=1`, overlay translated field values using the effective language.

This is easier to deploy safely for React clients because it makes the contract explicit and avoids surprising existing consumers.

#### Option 3 — Add dedicated translated endpoints

Example:

- `/api/method/my_app.api.get_translated_doc`
- `/api/method/my_app.api.get_translated_list`

This is the safest short-term frontend contract, but it does not satisfy the long-term goal of transparent standard API behavior.

### E. Recommendation to append to the design

For this proposal, the most practical rollout plan is:

1. **Phase 1:** implement backend translation overlay helpers plus explicit endpoints/params for React clients (`with_translations=1`).
2. **Phase 2:** extend standard `frappe.client.get`, `frappe.client.get_value`, `frappe.client.get_list`, and `/api/resource` behavior to honor the same translation service using resolved request language.
3. **Phase 3:** once compatibility is proven, make translated-value resolution the default for eligible fields in standard read APIs.

That means the immediate fix for a React app is **not** merely "change the frontend param and core will handle it". Instead, one of the following backend changes is required:

- customize the existing read endpoints to overlay translations, or
- add an explicit `with_translations` API mode/endpoints and update the React app to call that mode.

### 7. Existing interception points and hooks

There is no dedicated core "translate field values on load" hook.

What does exist:

- `doc_events` hooks, composed through `Document.hook(...)`, can run around standard document methods such as `validate`, `before_save`, `on_update`, `on_change`, etc.
- `onload` can run after a document is fetched for desk form loading (`frappe.desk.form.load.getdoc`), but `onload` does **not** participate in plain `frappe.get_doc()` value hydration.
- `permission_query_conditions` can alter list query filtering, but not rewrite values.
- `override_whitelisted_methods` can replace specific whitelisted endpoints, but not every internal ORM access path.

So there are hooks around lifecycle and API endpoints, but not a single first-class hook that transparently rewrites field values for all retrieval methods.

### 8. Existing translation infrastructure

Frappe currently has two relevant translation systems.

#### System 1: UI / static string translation (`_()`, CSV/PO, `frappe.local.lang`)

This is the primary built-in translation system.

Characteristics:

- Source strings are extracted from Python, JS, Jinja, DocType labels/options/descriptions, reports, custom fields, etc.
- Translations are loaded from app translation files plus user-maintained `Translation` records.
- Runtime lookup uses `_()` / `__()` against the merged translation dictionary for `frappe.local.lang`.

Scope:

- UI labels
- messages
- DocType labels and select options
- any string treated as a translation key

Non-scope:

- arbitrary document field values entered by users and stored in tables like `tabItem.item_name`

#### System 2: `Translation` DocType / user translations

Frappe also includes a `Translation` DocType with fields:

- `language`
- `source_text`
- `translated_text`
- `context`

These records are merged into the runtime translation dictionary by `get_user_translations(lang)`.

This mechanism is **not** keyed by `{doctype, docname, fieldname}`. It is keyed by source string text (plus optional context). That makes it suitable for translating known strings and labels, but unsuitable as a canonical storage for multilingual document data because:

- identical source strings across multiple records collide conceptually,
- it cannot distinguish two documents with the same default text but different intended translations,
- it is not bound to document permissions or record lifecycle,
- it does not express fallback semantics per field instance.

### 9. Definitive current-state conclusion

**Native Frappe today does not provide a first-class database-level translation system for user-generated DocType field values.**

What exists natively:

- metadata translation for labels/options/descriptions,
- runtime translation dictionaries keyed by source strings,
- limited formatting/export behavior for fields marked `translatable`.

What does not exist natively:

- a per-document, per-field, per-language store for translated field values,
- transparent substitution of translated user content in `frappe.get_doc`, `frappe.get_value`, `frappe.get_list`, or `/api/resource/`,
- built-in fallback rules for document content translations such as `item_name` in Arabic/Malayalam/English.

### 10. Ambiguities and assumptions

Ambiguity:

- The `translatable` field property name could be interpreted as database-content translation support.

Observed behavior:

- Core usage shows it is applied to translation lookup/export formatting, not to a dedicated multilingual content store.

Assumption used in this design document:

- Any proposed solution must introduce an explicit content-translation persistence model because the current `Translation` DocType is not sufficient for document-instance data.

## Problem Statement

In multilingual Frappe deployments, user-generated content stored in DocType fields cannot currently be stored and retrieved natively as language-specific values through the standard ORM and REST APIs.

Examples of affected data:

- `Item.item_name`
- `Item.description`
- category labels stored in custom doctypes
- any other user-managed `Data`, `Text`, `Small Text`, `Text Editor`, or `Select` value intended for multilingual display

Required behavior:

- A user whose effective language is Arabic (`ar`) should receive Arabic field values when available.
- If an Arabic translation does not exist for a field, Frappe should fall back to the default stored value.
- This behavior must hold consistently across:
  - `frappe.get_doc(doctype, name)`
  - `frappe.get_value(...)`
  - `frappe.get_list(...)`
  - REST resource endpoints under `/api/resource/` and equivalent v2 document endpoints

Concrete example:

- `frappe.get_doc("Item", "ITEM-001")` executed in a request context whose resolved language is `ar` should return `item_name` in Arabic if a translation exists, else the stored default value.

## Design Options

### Option A — Translation Child Table per DocType

#### Architecture overview

For each translatable business DocType, add a dedicated child table such as `Item Translation` attached to the parent document.

Example row shape:

- `language`
- `field_name`
- `translated_value`

#### Storage model

- Parent doctype keeps the canonical default-language values in its normal columns.
- Child table stores zero or more translated variants per field.
- Each parent document carries its own translations.

#### Fetch behavior

Potential implementation patterns:

- use a custom helper `get_translated_doc(doc)` after `frappe.get_doc()`, or
- patch `Document.as_dict()` / API serializers for specific doctypes, or
- use controller-specific methods to overlay translated values before returning.

#### Compatibility

- Works cleanly inside a custom app.
- Can be implemented without a core fork.
- Hard to make globally transparent for all doctypes unless additional wrappers/overrides are added.

#### Pros

- Simple mental model for a small number of doctypes.
- Strong parent-child referential locality.
- Easy to manage in forms for one doctype at a time.

#### Cons

- Schema explosion: one translation child doctype per translated business doctype.
- Hard to make generic across arbitrary doctypes.
- Poor fit for `frappe.get_list()` because list queries would need special joins per doctype.
- Harder to retrofit across many existing doctypes.

#### Complexity / maintenance

- Moderate for one doctype.
- High across many doctypes.
- Operational burden grows linearly with the number of translated doctypes.

### Option B — Central Translation Table

#### Architecture overview

Introduce one generic DocType, e.g. `DocType Field Translation`, keyed by document identity + field + language.

Recommended row shape:

- `ref_doctype`
- `docname`
- `field_name`
- `language`
- `translated_value`
- optional `source_value_hash` / `source_value_snapshot`
- optional `idx` for child-row support in a later phase

#### Storage model

- Base document tables continue storing the canonical default value.
- All translated overrides live in one normalized table.
- Unique constraint on `(ref_doctype, docname, field_name, language)`.

#### Fetch behavior

Build a translation resolution service in a custom app:

- resolve effective language using existing Frappe language priority,
- batch-fetch translations for the requested document(s),
- overlay translated values only for fields declared eligible/translatable,
- fall back to stored values when no translation exists.

For `get_list`, fetch list rows first, then batch-apply translations for all `(docname, field_name)` pairs in the page.

#### Compatibility

- Works in a custom app.
- Upgrade-safe if integration points are chosen carefully.
- Can support Python APIs and REST APIs through wrappers/endpoint overrides.

#### Pros

- Generic across all doctypes.
- Single schema to maintain and index.
- Easier analytics, caching, and batch retrieval.
- Best balance between normalization and framework compatibility.

#### Cons

- Requires a translation overlay layer for each retrieval path.
- `frappe.get_value()` and `frappe.get_list()` need explicit interception because they do not hydrate through one universal translation hook.
- Some monkey-patching or method overriding is still needed for transparency.

#### Complexity / maintenance

- Moderate initial implementation cost.
- Low-to-moderate long-term schema burden.
- Best long-term maintainability for an app-level solution.

### Option C — Override `frappe.get_doc` / `frappe.get_value` / REST in a custom app

#### Architecture overview

Build a custom app that intercepts retrieval APIs and transparently injects translated field values based on the active language.

This option is an integration strategy more than a storage model; it can be paired with Option A or B. In practice, it is most viable when paired with a **central translation table**.

#### Storage model

- Usually central table (recommended) or per-doctype child tables.

#### Fetch behavior

Possible hooks:

- monkey-patch `frappe.get_doc`
- monkey-patch `frappe.get_value`
- monkey-patch `frappe.get_list`
- override whitelisted methods like `frappe.client.get`, `frappe.client.get_value`, and REST handlers
- wrap `Document.as_dict()` for API serialization

#### Compatibility

- No core fork required.
- Highest risk among app-level solutions because monkey-patches are sensitive to upstream refactors.

#### Pros

- Can be made transparent to existing application code.
- Meets the requirement that standard APIs behave differently without changing every caller.

#### Cons

- Monkey-patching core entry points is brittle.
- Hard to guarantee coverage for all code paths, especially internal direct `frappe.db.get_value()` uses.
- Potential interaction risks with caching, permission logic, and third-party apps.

#### Complexity / maintenance

- High.
- Testing burden is substantial.
- Acceptable only if patch surface is kept very small and paired with narrow, well-documented wrappers.

### Option D — Core contribution: native `translatable` field property with framework-managed storage

#### Architecture overview

Enhance Frappe core so `DocField.translatable = 1` means true per-document content translation, backed by a core-managed storage convention.

Possible native design:

- introduce a framework DocType such as `Document Field Translation`, or
- introduce a reserved child table convention such as `__translations`.

#### Storage model

Core-managed normalized rows:

- `doctype`
- `docname`
- `fieldname`
- `language`
- `value`

#### Fetch behavior

Core would transparently resolve translated values inside:

- `Document.load_from_db()` / `get_doc`
- `DatabaseQuery.execute()` / `get_list`
- `db.get_value()` / `frappe.get_value`
- REST response serializers

#### Compatibility

- Cleanest architecture.
- Requires framework changes and upstream acceptance.
- Out of scope for a no-fork deployment in the short term.

#### Pros

- Semantically correct use of `translatable`.
- Best developer ergonomics.
- Lowest duplication once upstreamed.

#### Cons

- Requires a core PR and release adoption.
- Not immediately available to existing projects.
- Migration and backward-compatibility design would take time.

#### Complexity / maintenance

- High upfront, low after upstream adoption.
- Best long-term answer, but not the best immediate deployment answer.

### Option E — Explicit translated API surface without overriding core ORM

#### Architecture overview

Instead of changing standard retrieval APIs, expose new methods such as:

- `frappe.translate_doc(doctype, name, lang=None)`
- `frappe.get_translated_list(...)`

#### Storage model

- Typically the same as Option B.

#### Fetch behavior

- Callers opt in explicitly.
- Standard Frappe APIs remain unchanged.

#### Compatibility

- Very safe.
- Does not satisfy the requirement that existing standard APIs transparently return localized values.

#### Pros

- Lowest framework risk.
- Easy to reason about and test.

#### Cons

- Fails the main requirement.
- Existing apps and integrations must all be updated.

#### Complexity / maintenance

- Low.
- Rejected for this problem because the requirement is transparent standard-API behavior.

## Comparative Analysis Table

| Option | Storage model | Works without core fork | Can cover `get_doc` | Can cover `get_value` | Can cover `get_list` | Can cover REST | Upgrade safety | Complexity | Notes |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| A. Child table per DocType | per-parent child rows | Yes | Partial | Partial | Weak | Partial | Medium | Medium-High | Good for isolated doctypes, poor generality |
| B. Central translation table | normalized generic rows | Yes | Yes, with overlay layer | Yes, with overlay layer | Yes, with batch overlay | Yes | Good | Medium | Best app-level storage design |
| C. Custom app overriding core APIs | depends on storage choice | Yes | Yes | Yes | Yes | Yes | Medium-Low | High | Necessary as an integration strategy, not sufficient alone |
| D. Core native translatable fields | core-managed | No (requires PR) | Yes | Yes | Yes | Yes | Excellent after upstreaming | High upfront | Cleanest long-term architecture |
| E. New translated APIs only | normalized generic rows | Yes | No (standard APIs unchanged) | No | No | No | Excellent | Low | Does not meet requirements |

## Recommendation with Rationale

### Recommended approach

**Recommend Option B (Central Translation Table) combined with a minimal, well-scoped version of Option C (custom-app interception layer).**

This combination is the best fit for the stated constraints:

- **consistent with Frappe conventions:** metadata-driven, DocType-based, and language resolution aligned with `frappe.local.lang`
- **upgrade-safe:** avoids forking core and keeps invasive patching limited to a thin integration layer
- **covers standard APIs:** can be applied to `frappe.get_doc`, `frappe.get_value`, `frappe.get_list`, and REST endpoints
- **generic:** works across standard and custom doctypes without creating one child table per doctype

### Why not Option A alone

Option A does not scale cleanly across arbitrary doctypes and makes generic list/query translation much harder.

### Why not Option C alone

Option C by itself answers *where to intercept* but not *how to persist translations correctly*. Without a normalized storage model, it becomes brittle and inconsistent.

### Why not Option D as the primary recommendation

Option D is architecturally strongest, but it violates the constraint that the solution must not require a Frappe fork or immediate core change.

### Design stance

The practical recommendation is:

1. store translations in one central DocType,
2. declare which fields are eligible for translation using existing metadata (`translatable`) plus optional doctype-level policy,
3. resolve language with Frappe's existing priority,
4. overlay translated values late in the read path,
5. leave database canonical values untouched,
6. always fall back to stored values when no translation exists.

## Proposed Schema (recommended option)

### 1. New DocType: `DocType Field Translation`

Suggested JSON definition:

```json
{
  "doctype": "DocType",
  "name": "DocType Field Translation",
  "module": "Core",
  "custom": 1,
  "autoname": "hash",
  "istable": 0,
  "track_changes": 1,
  "field_order": [
    "ref_doctype",
    "docname",
    "field_name",
    "language",
    "translated_value",
    "source_value",
    "source_hash"
  ],
  "fields": [
    {
      "fieldname": "ref_doctype",
      "fieldtype": "Link",
      "label": "Reference DocType",
      "options": "DocType",
      "reqd": 1,
      "in_list_view": 1,
      "search_index": 1
    },
    {
      "fieldname": "docname",
      "fieldtype": "Dynamic Link",
      "label": "Document Name",
      "options": "ref_doctype",
      "reqd": 1,
      "in_list_view": 1,
      "search_index": 1
    },
    {
      "fieldname": "field_name",
      "fieldtype": "Data",
      "label": "Field Name",
      "reqd": 1,
      "in_list_view": 1,
      "search_index": 1
    },
    {
      "fieldname": "language",
      "fieldtype": "Link",
      "label": "Language",
      "options": "Language",
      "reqd": 1,
      "in_list_view": 1,
      "search_index": 1
    },
    {
      "fieldname": "translated_value",
      "fieldtype": "Long Text",
      "label": "Translated Value",
      "reqd": 1
    },
    {
      "fieldname": "source_value",
      "fieldtype": "Long Text",
      "label": "Source Value Snapshot"
    },
    {
      "fieldname": "source_hash",
      "fieldtype": "Data",
      "label": "Source Hash",
      "read_only": 1
    }
  ],
  "permissions": [
    {
      "role": "System Manager",
      "read": 1,
      "write": 1,
      "create": 1,
      "delete": 1
    },
    {
      "role": "Translator",
      "read": 1,
      "write": 1,
      "create": 1,
      "delete": 1
    }
  ]
}
```

### 2. Validation rules

Server-side validation should enforce:

- `ref_doctype` exists,
- `field_name` exists on the target doctype,
- target field is one of the supported translatable content field types,
- target field metadata is marked `translatable = 1`,
- one unique translation row per `(ref_doctype, docname, field_name, language)`.

### 3. Recommended indexes

At minimum:

- composite unique index: `(ref_doctype, docname, field_name, language)`
- lookup index: `(ref_doctype, docname, language)`
- optional lookup index: `(language, ref_doctype)`

### 4. Optional future extension

To support child table row translations later, add optional fields:

- `parentfield`
- `child_doctype`
- `child_docname`

Those should be deferred to phase 2 to keep the first implementation focused on top-level document fields.

## API Behavior Specification

### Language resolution

Use this resolution order for translated content:

1. explicit request override, if provided (`frappe.form_dict._lang` or function arg)
2. `frappe.local.lang`
3. current user preference
4. system default language
5. fallback to stored source value

This mirrors current Frappe language intent while ensuring content translation falls back safely.

### `frappe.get_doc(doctype, name)`

#### Without translation row

- returns the document exactly as stored.

#### With translation row

- load stored document normally,
- inspect doctype meta for translatable fields,
- fetch translation rows for `(doctype, name, effective_lang)`,
- overlay translated values onto the in-memory `Document`,
- preserve original source values in a private structure such as `doc._translated_source_values` for debugging/auditing.

#### Proposed behavior notes

- do not write translated values back to the base table,
- do not modify `modified` timestamps,
- do not affect save behavior unless explicitly editing translations.

### `frappe.get_value(doctype, filters, fieldname, ...)`

#### Without translation row

- return stored DB value.

#### With translation row

- if `fieldname` is one translatable field, resolve translation for the matched document and return translated value,
- if `fieldname` is a list, overlay translations only for eligible fields,
- if filters match multiple rows, existing semantics remain unchanged; translation applies only to the returned first row.

### `frappe.get_list(doctype, fields, filters, ...)`

#### Without translation rows

- return standard DB results.

#### With translation rows

- execute normal list query first,
- collect docnames from the page,
- determine which requested fields are translatable,
- batch-fetch translation rows for `(doctype, docnames[], requested_fields[], effective_lang)`,
- overlay translated values into the result rows,
- fields not requested are not translated.

#### Important constraint

For list performance, translation overlay should only apply to explicitly requested fields, not `*`, unless the caller explicitly opts in or the implementation expands `*` to permitted fields first.

### REST API `/api/resource/<doctype>/<name>` and v2 document read

- must behave the same as `frappe.get_doc(...).as_dict()` after translation overlay,
- translated values appear in the returned JSON,
- fallback remains the stored source value.

### REST list endpoints `/api/resource/<doctype>`

- must behave the same as `frappe.get_list(...)` plus overlay,
- only requested/listed eligible fields are translated.

### Save/update behavior

- standard document update endpoints continue to write source/canonical values to the base doctype table,
- translation rows should be managed through dedicated translation APIs or a translation-aware service layer,
- saving a translated overlay through the normal document save path should be avoided unless the request is explicitly marked as editing translations.

### Permissions behavior

- document permission checks must run on the base document before translated values are returned,
- translation row access should not bypass base doctype permissions,
- translation rows should inherit visibility from the target document by service-layer enforcement.

### Caching behavior

Recommended cache key shape:

- `(doctype, docname, language)` for document overlay cache,
- `(doctype, tuple(docnames), tuple(fields), language)` for batch list overlays.

Invalidate on:

- translation row create/update/delete,
- base document update for translatable fields,
- doctype metadata changes affecting translatable field eligibility.

## Implementation Roadmap

### Phase 1 — Research-to-code foundation

- create `DocType Field Translation`
- add validation logic and unique index
- add service helpers:
  - `get_effective_language()`
  - `get_translatable_fieldnames(doctype)`
  - `get_field_translations(doctype, docnames, fieldnames, lang)`
  - `overlay_translations_on_doc(doc, lang=None)`
  - `overlay_translations_on_list(doctype, rows, fields, lang=None)`

### Phase 2 — Safe API integration

- integrate with `frappe.client.get`
- integrate with `frappe.client.get_value`
- integrate with REST v1/v2 read/list endpoints
- provide optional wrappers for direct Python usage:
  - `get_translated_doc(...)`
  - `get_translated_list(...)`
- add a small monkey-patch only if transparent `frappe.get_doc` / `frappe.get_list` behavior is mandatory for all app code

### Phase 3 — Transparent ORM coverage

- carefully patch top-level `frappe.get_doc`, `frappe.get_value`, and `frappe.get_list`
- avoid patching `frappe.db.get_value` globally in phase 1; treat that as a separate explicit design decision
- add feature flags to disable translation overlay per site or per request for debugging

### Phase 4 — Authoring and maintenance workflows

- translation management DocType views / reports
- background jobs for detecting stale translations when source values change
- optional bulk import/export of translated content

### Phase 5 — Hardening

- benchmark list view overhead
- add caching and cache invalidation
- verify behavior with custom fields, child tables, report views, website routes, and integrations
- document failure/fallback behavior thoroughly

## Final conclusion

Frappe's current architecture is metadata-driven and translation-aware for UI strings, labels, and source-string lookup, but it does **not** natively support multilingual storage and transparent retrieval of user-generated document field values.

For a production-safe, upgrade-safe solution that does not fork Frappe core, the best design is:

- **centralized translation storage** for `{doctype, docname, field_name, language}` overrides,
- **language resolution aligned with Frappe's existing request/user/system logic**, and
- **a thin custom-app read-path overlay** for `get_doc`, `get_value`, `get_list`, and REST endpoints.

That approach delivers the required behavior while staying closest to Frappe's conventions and minimizing long-term maintenance risk.

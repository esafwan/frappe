# Query Reports

## What a Query Report is

In this repo version, a Query Report is a `Report` document where:

- `report_type = "Query Report"`
- SQL is stored in `Report.query`
- optional explicit column metadata lives in child table `Report.columns`
- optional filter metadata lives in child table `Report.filters`
- frontend route is still the generic `query-report/<name>` page

Primary sources:

- `frappe/core/doctype/report/report.py`
- `frappe/desk/query_report.py`
- `frappe/core/doctype/report/report.json`

## Storage model

### SQL storage

`Report.execute_query_report()` reads `self.query` directly. There is no separate Python module or SQL file loader for query reports in this code path.

Runtime steps:

1. ensure `query` exists
2. call `check_safe_sql_query(self.query)`
3. open read-only DB transaction
4. execute `frappe.db.sql(self.query, filters)`
5. infer columns from `self.columns` or DB cursor description
6. rollback read-only transaction

Implications:

- SQL parameter substitution uses the `filters` dict passed to `frappe.db.sql`
- query reports are DB-backed first-class documents
- standard query reports can still be exported as JSON files because the `Report` document itself is exported

## Backend execution path

### Canonical chain

1. client loads route in `query_report.js`
2. client requests `frappe.desk.query_report.get_script(report_name)`
3. client eventually calls `frappe.desk.query_report.run(...)`
4. `run()` calls `get_report_doc(report_name)`
5. `run()` calls `generate_report_result(...)` unless prepared-report path is active
6. `generate_report_result()` calls `get_report_result(report, filters)`
7. `get_report_result()` dispatches to `report.execute_query_report(filters)`
8. query result is normalized into canonical payload dict

### Relevant functions

| Dotted path | Role |
| --- | --- |
| `frappe.desk.query_report.get_report_doc` | resolves report/custom-report overlays and permission checks |
| `frappe.desk.query_report.run` | whitelisted runtime endpoint |
| `frappe.desk.query_report.generate_report_result` | canonical payload builder |
| `frappe.core.doctype.report.report.Report.execute_query_report` | SQL execution |

## Column contract for query reports

Query reports support two column sources.

### 1. Explicit columns from `Report.columns`

If child-table columns exist, `execute_query_report()` returns those dicts. These survive into `generate_report_result()` where each column is normalized by `get_column_as_dict()`.

Resulting dict fields commonly include:

- `fieldname`
- `label`
- `fieldtype`
- `options`
- `width`

### 2. Inferred columns from DB cursor description

If no explicit columns exist, backend uses `frappe.db.get_description()` and emits plain strings. Later `get_column_as_dict()` interprets string columns in formats such as:

- `Label`
- `Label:Fieldtype`
- `Label:Fieldtype/Options`
- `Label:Fieldtype:Width`

If no explicit `fieldname` is present, fieldname becomes `scrub(label)`.

## Filter model

### Where filters are defined

Filters can come from several places:

1. JS config in standard/non-standard report JS (`frappe.query_reports[report_name].filters`)
2. DB child table `Report.filters`
3. Custom report overrides stored in `Custom Report.json.filters`
4. route options / query parameters in Desk route

### How frontend loads filter metadata

- `query_report.js` calls `frappe.desk.query_report.get_script`
- `get_script()` returns:
  - `script`
  - `filters` (from `Report.filters` child rows)
  - `custom_report_name` if custom report context applies
- Client evals the script. If script did not define `filters`, it falls back to `report_doc.filters`.

### How filters are submitted

Client `refresh()` builds a filter dict from UI controls via `get_filter_values()` and sends it as `args.filters` to `frappe.desk.query_report.run`.

Special handling:

- wildcard filters wrap text with `%...%`
- mandatory filters are enforced in client before call when `raise=true`
- when viewing a prepared report, `prepared_report_name` is injected
- `js_filters` sends a simplified list of active link filters so backend can permission-check them even if filter definitions exist only in JS

## Permission / security checks specific to query reports

### Report document access

`get_report_doc()` enforces:

1. `Report.is_permitted()` — report role whitelist / custom role override
2. `frappe.has_permission(report.ref_doctype, "report")`
3. disabled flag rejection

### Link filter target access

`validate_filters_permissions(report_name, filters, user, js_filters)` iterates report-defined and JS-defined filters. For each filter where:

- field is present in incoming filters, and
- filter fieldtype is `Link`

it checks whether the user has `read` or `select` permission on the linked record referenced by the filter value.

This is a key guard for external UI designs: if you bypass `run()` and call lower layers directly, you must replicate this check.

### SQL safety

`Report.execute_query_report()` calls `check_safe_sql_query(self.query)` before execution.

This means user-authored SQL is filtered by Frappe's safe-SQL validator. The exact validator implementation was not expanded here, but the existence of this gate is code-proven.

## Canonical response contract

After `generate_report_result()`, query report responses are shaped as:

```python
{
  "result": list[dict],
  "columns": list[dict],
  "message": Any | None,
  "chart": dict | None,
  "report_summary": list | None,
  "skip_total_row": 0 | 1,
  "status": None,
  "execution_time": float | int,
  "add_total_row": bool,
  # optional: "custom_filters" when custom report defaults were applied
}
```

For pure query reports, normally only `columns`, `result`, `execution_time`, and `add_total_row` matter; `message/chart/report_summary` are typically absent because SQL execution returns only `[columns, result]`.

## Custom reports derived from query reports

Custom query reports do **not** replace SQL. Instead they wrap a reference report.

Mechanism:

- `Report.report_type = "Custom Report"`
- `Report.reference_report = <base report>`
- `Report.json` contains saved `columns` and `filters`
- `get_report_doc()` resolves the referenced report recursively and attaches:
  - `doc.custom_columns`
  - `doc.custom_filters`
  - `doc.custom_report = <original custom report name>`
  - `doc.is_custom_report = True`

In `run()`, if `are_default_filters` is true and the resolved report has `custom_filters`, backend substitutes them in place of the current filter payload.

## Exports

Whitelisted endpoint: `frappe.desk.query_report.export_query`

Key behavior:

- checks `can_export` on `report.ref_doctype`
- can run synchronously or in background email job
- internally calls `run()` again with `skip_total_calculation` and custom columns
- supports CSV and Excel
- can include filters, visible-row subset, indentation, and hidden columns

## Practical implications for reimplementation

### Minimum server abstraction needed

For a custom UI, the smallest faithful wrapper around query reports should expose:

1. `get_report_metadata(name)`
   - report doc basics
   - client JS string or normalized filter schema
2. `run_report(name, filters, options)`
   - uses existing `frappe.desk.query_report.run`
3. `export_report(name, filters, visible_columns, visible_rows, format)`
   - proxies `frappe.desk.query_report.export_query`

### Avoid generating raw SQL from LLMs unsafely

Recommended policy:

- allow LLMs to generate structured report intent, not final SQL directly
- compile into safe query builder templates or vetted SQL subset
- let backend validate with `check_safe_sql_query`
- require human review before persisting `Report.query`

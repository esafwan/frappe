# Script Reports

## What a Script Report is

A Script Report is a `Report` document with `report_type = "Script Report"` whose result is produced by Python code instead of stored SQL.

Frappe supports **two script report execution modes**.

| Mode | Where Python lives | How discovered |
| --- | --- | --- |
| Standard script report | App module file `<module>/report/<report>/<report>.py` | `Report.execute_module()` computes dotted path and imports `<path>.execute` |
| Non-standard / custom DB script report | `Report.report_script` | `Report.execute_script()` runs code through `safe_exec()` |

Optional frontend JS can also be file-backed or DB-backed.

## File layout for standard script reports

Convention from `get_report_module_dotted_path(module, report_name)`:

- Python: `<app>.<module>.report.<scrub(report_name)>.<scrub(report_name)>.execute`
- JS: loaded by `query_report.get_script()` from matching `.js` file in same folder
- HTML print template: optional `.html` file in same folder

Boilerplates are defined in:

- `frappe/core/doctype/report/boilerplate/controller.py`
- `frappe/core/doctype/report/boilerplate/controller.js`

## Script report execution path

1. client route enters `query_report.js`
2. backend metadata fetched by `frappe.desk.query_report.get_script`
3. run request hits `frappe.desk.query_report.run`
4. `get_report_result(report, filters)` dispatches to `Report.execute_script_report(filters)`
5. `execute_script_report()` chooses:
   - `execute_module(filters)` if standard
   - `execute_script(filters)` otherwise
6. result tuple/list is normalized by `generate_report_result()`

## Standard script report Python contract

Boilerplate documents the canonical form:

```python
def execute(filters: dict | None = None):
    columns = get_columns()
    data = get_data()
    return columns, data
```

But runtime supports more than two return values.

### Full supported return arity

`generate_report_result()` calls `ljust_list(res, 6)` and interprets values as:

1. `columns`
2. `result`
3. `message`
4. `chart`
5. `report_summary`
6. `skip_total_row`

Therefore a script report can return any prefix of:

```python
return columns, data
return columns, data, message
return columns, data, message, chart
return columns, data, message, chart, report_summary
return columns, data, message, chart, report_summary, skip_total_row
```

## Extra return fields a script report may emit

### `message`

Displayed by `query_report.js` via `show_status(data.message)` when not in prepared-report mode.

### `chart`

Client uses `get_chart_options(data)` to prefer:

- `report_settings.get_chart_data(columns, result)` if JS supplies it, else
- `data.chart`

Expected chart payload format is Frappe Charts config-like, typically:

```python
{
  "data": {
    "labels": [...],
    "datasets": [{"name": ..., "values": [...]}]
  },
  "type": "bar" | "line" | ...,
  "fieldtype": "Currency" | ... ,   # optional for tooltip formatting
  "options": ...                      # optional field options
}
```

### `report_summary`

Client renders each item with `frappe.utils.build_summary_item`. Typical summary entries are dicts containing label/value/indicator metadata.

### `skip_total_row`

If truthy, backend suppresses total-row addition even when report has `add_total_row` enabled.

## Non-standard DB script report contract

Implemented in `Report.execute_script()`.

Execution environment:

```python
loc = {
  "filters": frappe._dict(filters),
  "data": None,
  "result": None,
}
safe_exec(self.report_script, None, loc, script_filename=f"Report {self.name}")
```

After execution:

- if script sets `data`, backend returns `data` verbatim
- else backend returns `(self.get_columns(), loc["result"])`

This gives two DB-script authoring styles.

### Old-style explicit `data`

```python
data = [columns, result]
```

or even the full 6-element structure.

### New-style `result` only

```python
result = [...]
```

with columns taken from the `Report.columns` child table.

Tests in `frappe/core/doctype/report/test_report.py` verify both styles.

## Filters passed into script reports

- Standard file-backed report: `execute(filters)` receives `frappe._dict(filters)`
- DB script report: `filters` is injected into safe-exec locals as `frappe._dict`

Client passes filters as plain JSON-like key/value map.

## JS pairing for script reports

Client behavior is identical to query reports:

- report page loads JS via `get_script()`
- file JS is preferred over DB `Report.javascript`
- JS should register `frappe.query_reports[report_name] = {...}`

JS responsibilities can include:

- filter definitions
- `onload(report)` hooks
- custom formatter
- `after_refresh(report)`
- `get_chart_data(columns, result)`
- `get_datatable_options(opts)`
- `get_pdf_format(...)`
- custom action buttons

## Prepared-report interaction for script reports

`Report.execute_script_report()` includes a timer-based heuristic:

- if report is not already marked `prepared_report`
- start a 15-second timer that calls `enable_prepared_report(report, site)`
- if execution runs long enough, future runs will default to prepared-report mode

This is important: **script reports can auto-promote themselves into prepared reports** after slow executions.

## Example in Frappe core

`frappe/core/report/database_storage_usage_by_tables/database_storage_usage_by_tables.py`

Notable features:

- `execute(filters=None)` returns explicit `COLUMNS, data`
- uses `frappe.only_for("System Manager")` for hard role gating inside report code
- exposes extra whitelisted helper `optimize_doctype()` used by report JS action button

This demonstrates that script report files often bundle additional APIs adjacent to `execute()`.

## Standard packaging behavior

`Report.export_doc()` exports the `Report` document JSON for standard reports.

For standard script reports, `Report.create_report_py()` also ensures report boilerplates are created:

- `controller.py`
- `controller.js`

That is how app-shipped reports become portable fixtures in source control.

## What a future external abstraction should preserve

A robust external script-report schema should normalize:

- `name`
- `ref_doctype`
- `filters_schema`
- `columns_schema`
- `execution_mode` (`module` vs `db_script`)
- `returns_chart` bool
- `returns_summary` bool
- `supports_total_row` bool
- `prepared_report_enabled` bool
- `client_hooks_present` (`formatter`, `onload`, etc.)

## AI / LLM safety guidance

Never allow an LLM to author unrestricted `report_script` directly in production.

Safer pattern:

1. LLM emits a high-level plan:
   - source doctypes
   - joins / metrics needed
   - filter schema
   - output columns
   - chart/summary intent
2. backend compiles into restricted templates or a safe DSL
3. human review gates conversion into Python/SQL
4. store generated artifacts as standard file-backed reports where possible for auditability

# Backend APIs and Methods

## High-value whitelisted APIs

### Query / script / custom report APIs

| Dotted path | File | Inputs | Returns | Notes |
| --- | --- | --- | --- | --- |
| `frappe.desk.query_report.get_script` | `frappe/desk/query_report.py` | `report_name` | `{script, html_format, execution_time, filters, custom_report_name}` | Metadata/bootstrap API for report page and related UX |
| `frappe.desk.query_report.run` | same | `report_name`, `filters`, `ignore_prepared_report`, `custom_columns`, `is_tree`, `parent_field`, `are_default_filters`, `js_filters`, `skip_total_calculation` | canonical report payload dict | Main safe API to expose to external UI |
| `frappe.desk.query_report.export_query` | same | form params | file response or background enqueue | Export for query/script/custom report page |
| `frappe.desk.query_report.get_data_for_custom_field` | same | `doctype`, `field`, `names` | `{name: value}` map | Used for client-added custom columns |
| `frappe.desk.query_report.save_report` | same | `reference_report`, `report_name`, `columns`, `filters` | custom report name | Saves a `Custom Report` |

### Report Builder / List report APIs

| Dotted path | File | Purpose |
| --- | --- | --- |
| `frappe.desk.reportview.get` | `frappe/desk/reportview.py` | compressed list/report-view fetch |
| `frappe.desk.reportview.get_list` | same | uncompressed fetch |
| `frappe.desk.reportview.get_count` | same | count API |
| `frappe.desk.reportview.save_report` | same | save report-builder report |
| `frappe.desk.reportview.delete_report` | same | delete report-builder report |
| `frappe.desk.reportview.export_query` | same | export report-builder results |
| `frappe.desk.reportview.get_sidebar_stats` / `get_stats` | same | sidebar aggregations |
| `frappe.desk.reportview.get_filter_dashboard_data` | same | filter widget stats |

### Prepared report APIs

| Dotted path | File | Purpose |
| --- | --- | --- |
| `frappe.core.doctype.prepared_report.prepared_report.make_prepared_report` | `prepared_report.py` | insert and queue background prepared report |
| `...stop_prepared_report` | same | stop queued/running job |
| `...get_reports_in_queued_state` | same | dedupe warning helper |
| `...delete_prepared_reports` | same | bulk delete old queued jobs |
| `...download_attachment` | same | download raw prepared JSON attachment |
| `...enqueue_json_to_csv_conversion` | same | background JSON->CSV conversion |

### Dashboard chart APIs

| Dotted path | File | Purpose |
| --- | --- | --- |
| `frappe.desk.doctype.dashboard_chart.dashboard_chart.get` | `dashboard_chart.py` | main chart data API for doctype-backed charts |
| `...create_dashboard_chart` | same | create chart record |
| `...create_report_chart` | same | create report-backed chart and optionally add to dashboard |
| `...add_chart_to_dashboard` | same | append chart link to dashboard |
| `...get_charts_for_user` | same | link-field search helper |
| `frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source.get_config` | `dashboard_chart_source.py` | returns JS source code for custom chart source |

## Important internal methods and call graph notes

### `frappe.desk.query_report.get_report_doc(report_name)`

Responsibilities:

- load `Report` doc
- if custom report, recursively resolve `reference_report`
- attach `custom_columns`, `custom_filters`, `is_custom_report`
- sync prepared-report flag from custom report wrapper
- enforce report and ref-doctype permissions
- reject disabled reports

### `frappe.core.doctype.report.report.Report.execute_query_report(filters)`

Input: filter dict

Output: `[columns, result]`

Side effects / details:

- `check_safe_sql_query`
- read-only transaction
- column inference via cursor description if no explicit columns

### `Report.execute_script_report(filters)`

Input: filter dict

Output: arbitrary 2-6 element report tuple/list

Side effects:

- slow-report timer can flip `prepared_report` on
- stores execution time in cache hash `report_execution_time`

### `frappe.desk.query_report.generate_report_result(...)`

This is the **canonical serializer** for report results.

Important outputs:

- coerces all columns to dict form
- coerces row lists to row dicts
- applies custom columns
- filters rows against user match conditions
- adds totals row
- includes message/chart/report summary

### `frappe.desk.query_report.get_prepared_report_result(...)`

Responsibilities:

- locate completed prepared report by canonicalized filters/user/report name if explicit doc name not given
- read attachment content via `PreparedReport.get_prepared_data()`
- support backwards compatibility for older stored formats
- return `{..., prepared_report: True, doc: prepared_report_doc}`

### `frappe.core.doctype.prepared_report.prepared_report.generate_report(prepared_report)`

Worker path:

1. update job id + set status `Started`
2. load `Prepared Report` and target `Report`
3. resolve custom-report columns if needed
4. call `generate_report_result(...)`
5. serialize compressed JSON attachment
6. set status `Completed` or `Error`
7. add Notification Log entry
8. publish realtime `report_generated`

### `frappe.desk.doctype.dashboard_chart.dashboard_chart.get(...)`

Dispatches chart generation based on chart type:

- `Group By` -> `get_group_by_chart_config`
- `Heatmap` -> `get_heatmap_chart_config`
- else time-series `get_chart_config`

All doctype-backed chart variants append docstatus `< 2` filter automatically.

## Methods especially safe/useful for external UI

### Best existing APIs to reuse directly

1. `frappe.desk.query_report.get_script`
2. `frappe.desk.query_report.run`
3. `frappe.desk.query_report.export_query`
4. `frappe.core.doctype.prepared_report.prepared_report.make_prepared_report`
5. `frappe.desk.doctype.dashboard_chart.dashboard_chart.get`
6. `frappe.desk.doctype.dashboard_chart_source.dashboard_chart_source.get_config` (only if you trust/evaluate source JS)

### APIs to wrap carefully rather than expose raw

- `frappe.desk.query_report.save_report`
  - mutates custom reports directly; validate names/ownership externally
- `frappe.desk.reportview.save_report`
  - builder-report persistence tied to Desk UX model
- `create_dashboard_chart` / `create_report_chart`
  - should be fronted by schema validation
- DB-script report editing through `Report` document writes
  - high risk for AI-generated content

## Supporting permission methods

| Method | Role |
| --- | --- |
| `frappe.boot.get_allowed_reports` / `get_allowed_report_names` | determines visible reports from roles/custom roles |
| `Report.is_permitted()` | per-report role whitelist logic |
| `frappe.has_permission(report.ref_doctype, "report")` | must hold to run a report |
| `validate_filters_permissions()` | checks link filter target records |
| `prepared_report.get_permission_query_condition()` / `has_permission()` | prepared report access derived from allowed reports |
| `dashboard_chart.get_permission_query_conditions()` / `has_permission()` | chart access derived from source permissions |

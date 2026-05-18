# Core DocTypes and Storage

## Storage overview

| Concept | DocType | SQL table | Key fields used at runtime |
| --- | --- | --- | --- |
| Report definition | `Report` | `tabReport` | `report_name`, `ref_doctype`, `report_type`, `query`, `report_script`, `javascript`, `json`, `prepared_report`, `disabled`, `module`, `roles`, `filters`, `columns` |
| Report filter metadata | `Report Filter` | child table `tabReport Filter` | `fieldname`, `label`, `fieldtype`, `options`, `mandatory`, `wildcard_filter`, `default` |
| Report column metadata | `Report Column` | child table `tabReport Column` | `fieldname`, `label`, `fieldtype`, `options`, `width` |
| Prepared output job | `Prepared Report` | `tabPrepared Report` | `report_name`, `filters`, `status`, `job_id`, `error_message`, `report_end_time`, `peak_memory_usage` |
| Dashboard chart definition | `Dashboard Chart` | `tabDashboard Chart` | `chart_type`, `report_name`, `document_type`, `filters_json`, `dynamic_filters_json`, `use_report_chart`, `x_field`, `y_axis`, `custom_options`, `timespan`, `time_interval`, `type`, `is_public`, `roles` |
| Dashboard chart Y-axis rows | `Dashboard Chart Field` | child table `tabDashboard Chart Field` | `y_field`, `color` |
| Custom chart source registry | `Dashboard Chart Source` | `tabDashboard Chart Source` | `source_name`, `module`, `timeseries` |
| Saved role override for report/page | `Custom Role` / single `Role Permission for Page and Report` UI | `tabCustom Role`, `tabHas Role` | per-report custom role overlays used by allowed report resolution |

## `Report` DocType field-level analysis

Source: `frappe/core/doctype/report/report.json`, runtime behavior in `frappe/core/doctype/report/report.py`.

### Core identity fields

| Field | Type | Meaning | Runtime use |
| --- | --- | --- | --- |
| `report_name` | Data, unique | Human/report identifier; also document name via `autoname: field:report_name` | Used as route name, lookup key, module folder name for standard reports |
| `ref_doctype` | Link -> `DocType` | Primary doctype the report is about | Required for permissions and list/report-builder execution |
| `module` | Link -> `Module Def` | Module used for file export of standard reports | Used to compute standard script module path |
| `is_standard` | Select `No/Yes` | Whether report is app-backed/exportable standard record | Controls edit restrictions and export to files |
| `disabled` | Check | Runtime disable switch | `get_report_doc()` throws if enabled flag is off |

### Report type and execution fields

| Field | Type | Applies to | Meaning |
| --- | --- | --- | --- |
| `report_type` | Select | all | One of `Report Builder`, `Query Report`, `Script Report`, `Custom Report` |
| `query` | Code(SQL) | Query Report | Raw SQL text executed by `frappe.db.sql()` after `check_safe_sql_query()` |
| `report_script` | Code(Python) | non-standard Script Report | DB-stored Python body run by `safe_exec()` |
| `javascript` | Code(JavaScript) | non-standard Script Report | DB-stored client report JS loaded when no file JS exists |
| `json` | Code(JSON) | Report Builder and Custom Report (and legacy storage) | Serialized config blob; for custom report stores custom columns/filters; for report builder stores fields/order/group/chart config |
| `reference_report` | Data | Custom Report | Name of base report to inherit execution from |
| `prepared_report` | Check | query/script/custom runtime | If enabled, `query_report.run()` prefers prepared-report retrieval path |
| `timeout` | Int | prepared reports | Overrides background job timeout in seconds |

### Output/post-processing flags

| Field | Type | Meaning |
| --- | --- | --- |
| `add_total_row` | Check | Ask runtime to append total row when possible |
| `add_translate_data` | Check | Exposed in metadata; runtime translation only happens when client passes `translate_data` filter flag |
| `letter_head` | Link -> `Letter Head` | Used by query report print/PDF UX for non-standard reports |

### Child tables

| Child field | Child DocType | Runtime role |
| --- | --- | --- |
| `filters` | `Report Filter` | Filter metadata sent to client from `get_script()` when report JS does not define filters itself |
| `columns` | `Report Column` | Explicit query/script report columns if defined in DB |
| `roles` | `Has Role` | Default role whitelist checked by `Report.is_permitted()` and by boot-time allowed-report enumeration |

## Standard vs custom persistence behavior

### Standard reports

- Marked `is_standard = "Yes"`.
- Saved only by Administrator in developer mode (`Report.validate`).
- Exported by `Report.export_doc()` to app files via `export_to_files(...)`.
- Standard **script** reports additionally generate boilerplate Python and JS files via `create_report_py()` if needed.
- On trash, standard report deletion is blocked outside developer/migrate/patch contexts.

### Non-standard reports

- Forced to `is_standard = "No"` unless administrator in developer mode.
- For non-builder, non-custom reports, only `Script Manager` may edit (`Report.validate`).
- DB is the source of truth for SQL, script, JS, filters, and columns.

### Custom reports

Custom reports are plain `Report` rows with:

- `report_type = "Custom Report"`
- `reference_report = <base report name>`
- `json = {"columns": [...], "filters": {...}}`

At runtime, `get_report_doc()` resolves the underlying reference report and overlays `custom_columns` / `custom_filters` onto it.

## `Report Filter` child table

Source: `frappe/core/doctype/report_filter/report_filter.json`

| Field | Meaning |
| --- | --- |
| `fieldname` | API/filter payload key |
| `label` | Client label |
| `fieldtype` | UI widget type; query runtime also inspects Link filters for permission checks |
| `options` | Link target DocType / Select options / field options |
| `mandatory` | Marks required filter in UI |
| `wildcard_filter` | Client wraps value with `%...%` before submission |
| `default` | Default filter value used by client/report charts |

## `Report Column` child table

Source: `frappe/core/doctype/report_column/report_column.json`

Used when report author wants explicit field metadata rather than inferred string columns.

| Field | Meaning |
| --- | --- |
| `fieldname` | canonical key used in result dicts |
| `label` | display label |
| `fieldtype` | formatting and total-row behavior |
| `options` | e.g. link target or currency field |
| `width` | client/export sizing hint |

## `Prepared Report` DocType

Source: `frappe/core/doctype/prepared_report/prepared_report.json`, behavior in `prepared_report.py`.

### Persisted DB fields

| Field | Meaning |
| --- | --- |
| `report_name` | Name of report being executed |
| `status` | `Queued`, `Started`, `Completed`, `Error` |
| `filters` | Canonically serialized JSON string of filter payload |
| `job_id` | Background worker job identifier |
| `error_message` | Traceback / execution failure details |
| `report_end_time` | Finish timestamp |
| `peak_memory_usage` | Worker-reported memory use |

### Virtual/display fields

| Field | Meaning |
| --- | --- |
| `queued_by` | virtual property mapping to owner |
| `queued_at` | virtual property mapping to creation |
| `filter_values` | HTML rendering of stored filters in form view |

### Actual report payload storage

The report rows/columns are **not stored in DB fields**. They are stored as a **private `File` attachment** containing compressed JSON (`.json.gz`) attached to the `Prepared Report` document.

## `Dashboard Chart` DocType

Source: `frappe/desk/doctype/dashboard_chart/dashboard_chart.json` + `.py`.

### Core identity / visibility

| Field | Meaning |
| --- | --- |
| `chart_name` | Doc name and user-facing label |
| `is_public` | Makes chart discoverable to all users with source permissions |
| `is_standard` / `module` | Standard export behavior analogous to standard reports |
| `roles` | Optional role whitelist overriding broader access |

### Chart source mode switch

| Field | Meaning |
| --- | --- |
| `chart_type` | One of `Count`, `Sum`, `Average`, `Group By`, `Custom`, `Report` |
| `document_type` | Doctype-backed chart source |
| `report_name` | Report-backed source |
| `source` | `Dashboard Chart Source` link for custom JS-defined sources |

### Doctype-backed chart config

| Field | Meaning |
| --- | --- |
| `based_on` | date/time field used for time series |
| `value_based_on` | numeric field aggregated for Sum/Average |
| `group_by_based_on` | field used for Group By chart labels |
| `aggregate_function_based_on` | field aggregated in group-by sum/avg |
| `parent_document_type` | required when charting child tables |
| `timeseries` | toggle between timeseries and categorical behavior |
| `timespan`, `from_date`, `to_date`, `time_interval`, `heatmap_year` | temporal slicing config |
| `type` | visual chart type: `Line`, `Bar`, `Percentage`, `Pie`, `Donut`, `Heatmap` |

### Report-backed chart config

| Field | Meaning |
| --- | --- |
| `use_report_chart` | if true, use the `chart` payload returned by the report itself |
| `x_field` | x-axis source field when deriving chart from report rows |
| `y_axis` | child rows (`Dashboard Chart Field`) specifying Y fields and colors |
| `filters_json` | static report filter payload |
| `dynamic_filters_json` | expressions evaluated client-side then merged into filters |

### Arbitrary overrides

| Field | Meaning |
| --- | --- |
| `custom_options` | JSON merged into chart args on client |
| `currency` | explicit currency formatting override |
| `color` | default color for single-series charts |
| `last_synced_on` | UI subtitle / freshness display |

## `Dashboard Chart Source`

Source: `frappe/desk/doctype/dashboard_chart_source/dashboard_chart_source.json` + `.py`.

Purpose: registry for **custom JS-backed chart sources**.

Stored fields:

- `source_name`: unique source identifier / docname
- `module`: module whose filesystem folder contains the JS source
- `timeseries`: source capability hint

Runtime detail:

- `get_config(name)` loads `<module>/dashboard_chart_source/<scrubbed_name>/<scrubbed_name>.js`
- client evals that JS and expects it to register `frappe.dashboards.chart_sources[<source_name>]`

## File-backed standard report/chart packaging

### Standard Script Report folder convention

Computed by `get_report_module_dotted_path(module, report_name)`:

`<app>.<scrub(module)>.report.<scrub(report_name)>.<scrub(report_name)>`

Typical files inside the module folder:

- `<module>/report/<report_name>/<report_name>.json` — exported `Report` document
- `<module>/report/<report_name>/<report_name>.py` — `execute(filters)`
- `<module>/report/<report_name>/<report_name>.js` — `frappe.query_reports[...]` config
- optional `<module>/report/<report_name>/<report_name>.html` — custom print template

### Standard Dashboard Chart Source folder convention

`<module>/dashboard_chart_source/<source_name>/<source_name>.js`

## What is DB-backed vs file-backed?

| Artifact | DB-backed? | File-backed? | Notes |
| --- | --- | --- | --- |
| Query report SQL | Yes | exported JSON for standard record only | authoritative field is `Report.query` |
| Standard script report Python | indirectly via `Report` record + module path | Yes | code loaded from module file at runtime |
| Non-standard script report Python | Yes (`report_script`) | No | executed via `safe_exec` |
| Report JS config | standard via file, custom/non-standard via `Report.javascript` | Yes for standard, optional HTML too | `get_script()` prefers file JS then falls back to DB JS |
| Report Builder config | Yes (`Report.json`) | standard reports may also be exported JSON | runtime reads JSON from document |
| Prepared result payload | metadata in DB; result blob in `File` attachment | attachment storage | compressed JSON |
| Dashboard Chart config | Yes | standard records exported as files in module | runtime reads doc |
| Custom chart source code | metadata in DB | Yes JS file | code loaded with `get_config()` |

# Frontend Reporting Layer

## Primary frontend files

| File | Responsibility |
| --- | --- |
| `frappe/public/js/frappe/views/reports/query_report.js` | Query/script/custom report page runtime |
| `frappe/public/js/frappe/views/reports/report_view.js` | Report Builder / saved list report runtime |
| `frappe/public/js/frappe/views/reports/report_utils.js` | Column parsing, chart helpers, export dialog |
| `frappe/public/js/frappe/widgets/chart_widget.js` | Dashboard chart widget runtime |
| `frappe/public/js/frappe/utils/dashboard_utils.js` | Fetching chart/report filters, merging dynamic filters |
| `frappe/core/doctype/report/report.js` | Report form UX, “Show Report” routing |
| `frappe/desk/doctype/dashboard_chart/dashboard_chart.js` | Dashboard Chart form UX, report field loading, preview |

## Query report page runtime

### Page bootstrap

File: `query_report.js`

- registers standard page `query-report`
- creates `frappe.query_report = new frappe.views.QueryReport(...)`
- route show handler calls `.show()`

### Metadata load

`QueryReport.load_report()` runs, in order:

1. `get_report_doc()`
2. `get_report_settings()`
3. `add_translate_data_checkbox()`
4. progress bar setup
5. page header setup
6. `refresh_report(route_options)`

### Report JS loading

`get_report_settings()`:

- if `frappe.query_reports[this.report_name]` already exists, reuse it
- else call `frappe.desk.query_report.get_script`
- eval returned JS
- use `custom_report_name` to resolve local settings name when dealing with custom reports
- if DB report doc has filters and JS did not define any, copy `report_doc.filters`

### Filter control construction

`setup_filters()` turns filter definitions into page fields.

Supported behaviors visible in code:

- default values
- `get_query`
- custom `on_change`
- `depends_on` evaluation for show/hide
- mandatory validation
- wildcard wrapping
- special grouped check-filter area
- collapsible filter UI

### Run action

`refresh()` constructs args and calls:

```js
frappe.call({
  method: "frappe.desk.query_report.run",
  type: "GET",
  args: {
    report_name,
    filters,
    ignore_prepared_report,
    is_tree,
    parent_field,
    are_default_filters,
    js_filters,
  }
})
```

### Payload consumption

On response:

- render prepared-report controls if `prepared_report`
- render summary if `report_summary`
- render status message if `message`
- call `prepare_report_data(data)`
- derive chart options from returned `chart` or `get_chart_data` JS hook
- render chart with `frappe.Chart`
- render datatable with `frappe-datatable`

### Datatable behavior

`render_datatable()` sets options including:

- `inlineFilters: true`
- `treeView`
- `showTotalRow`
- optional report-provided `get_datatable_options`
- optional `after_datatable_render`

### Client-side extension hooks used by reports

Hooks observed in `query_report.js`:

- `onload(report)`
- `after_refresh(report)`
- `formatter(value, row, column, data, default_formatter, filter)`
- `get_chart_data(columns, result)`
- `get_datatable_options(options)`
- `after_datatable_render(datatable)`
- `get_pdf_format(report, custom_format)`
- `initial_depth` for tree reports
- `tree` and `parent_field`
- `export_hidden_cols`
- `separate_check_filters`
- `collapsible_filters`

## How filter definitions are stored and loaded

### Storage sources

1. JS object literal in report JS file / `Report.javascript`
2. `Report.filters` child table rows
3. custom report saved filter values in `Custom Report.json.filters`

### Loading precedence

1. evaluate report JS if present
2. if JS object lacks `filters`, use `Report.filters`
3. when custom report with default filters is run and UI has not changed defaults, backend may return `custom_filters`, and client resets filters accordingly

## Report View frontend

File: `report_view.js`

### Purpose

This is not query-report runtime. It is a `ListView` subclass that adds:

- saved report-builder configs
- column add/remove/reorder
- group by
- chart configuration from list data
- save/delete report-builder reports

### Saved report loading

`setup_defaults()` checks route length. If saved report name exists:

- fetch `Report` doc
- parse `report_doc.json`
- extract `filters`, `order_by`, `page_length`, `group_by`, `chart_args`

### Save/delete APIs

- save builder report: `frappe.desk.reportview.save_report`
- delete builder report: `frappe.desk.reportview.delete_report`

### Charting in Report View

Unlike query reports, report view charts are derived client-side from list data.

- chart configuration stored in saved report JSON or user settings as `chart_args`
- chart built by `make_chart()` with `labels` and datasets from current list results

## Dashboard chart frontend

### Widget runtime

`chart_widget.js` handles three source types:

| Source | Method |
| --- | --- |
| Report | `frappe.desk.query_report.run` |
| Doctype/chart config | `frappe.desk.doctype.dashboard_chart.dashboard_chart.get` |
| Custom source | arbitrary method supplied by JS registered in `frappe.dashboards.chart_sources[...]` |

### Report-backed chart specifics

- filter dialog loads report filters via `frappe.report_utils.get_report_filters(report_name)`
- when filter dialog opens, it instantiates a temporary `frappe.views.QueryReport` so report JS `onload` hooks can operate on those filters
- if `use_report_chart` is set, widget consumes `result.chart.data`
- otherwise widget derives chart data from report result and chart doc’s `x_field` / `y_axis`

## Dashboard utilities

`dashboard_utils.js` provides:

- `get_filters_for_chart_type(chart)`
  - report-backed charts -> `report_utils.get_report_filters`
  - custom chart sources -> load source JS and return `chart_sources[source].filters`
- `get_all_filters(doc)`
  - merges static `filters_json` and evaluated `dynamic_filters_json`
- dynamic filter UI helpers

## Auto Email Report integration

`frappe/email/doctype/auto_email_report/auto_email_report.js` calls `frappe.desk.query_report.get_script` and references `frappe.query_reports[report]` to inspect report filters. This is additional evidence that **`get_script` is the metadata API shared across Desk features**, not just the report page.

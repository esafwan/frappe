# Report Runtime Flow

## 1. Query / Script / Custom report open flow

### Sequence

```text
User opens /desk/query-report/<Report>
  -> frappe/public/js/frappe/views/reports/query_report.js
  -> QueryReport.get_report_doc()
      -> frappe.model.with_doc("Report", report_name)
  -> QueryReport.get_report_settings()
      -> frappe.desk.query_report.get_script(report_name)
      -> eval returned JS
      -> merge DB filter metadata if JS lacks filters
  -> QueryReport.setup_filters()
  -> QueryReport.refresh()
      -> frappe.desk.query_report.run(...)
      -> generate_report_result(...)
      -> render summary/chart/datatable
```

## 2. Detailed backend flow for `frappe.desk.query_report.run`

### Step-by-step

1. `validate_filters_permissions(report_name, filters, user, js_filters)`
   - checks linked-record filter access
2. `get_report_doc(report_name)`
   - resolves custom reports to reference report
   - checks report roles, ref-doctype report permission, disabled flag
3. decide whether prepared-report path should be used:
   - requires `report.prepared_report`
   - skipped if `ignore_prepared_report` or `custom_columns`
4. if prepared-report mode:
   - possibly extract `prepared_report_name` from filters
   - call `get_prepared_report_result(...)`
5. else normal mode:
   - call `generate_report_result(...)`
6. set `add_total_row`
7. optionally include `custom_filters`
8. return payload dict

## 3. `generate_report_result()` internals

### Inputs

- report doc
- filters
- user
- custom columns
- tree options
- total-row control

### Operations

1. parse string filters if needed
2. `get_report_result(report, filters)` dispatches by report type
3. unpack up to 6 return values
4. normalize all column definitions with `get_column_as_dict()`
5. normalize row format into list of dicts if needed
6. overlay saved/unsaved custom columns
7. fetch custom-column linked values via `get_data_for_custom_field()`
8. permission-filter row data via `get_filtered_data()`
9. append totals if needed via `add_total_row()`
10. translate data if `translate_data` filter flag is present
11. return canonical response

## 4. Report Builder / Report View open flow

### Routes

Saved report-builder views use routes like:

- `List/<DocType>/Report`
- `List/<DocType>/Report/<saved_report_name>`

Frontend implementation: `frappe/public/js/frappe/views/reports/report_view.js`

### Sequence

```text
Open Report View
  -> ReportView.setup_defaults()
      -> if saved report, load Report doc and parse report_doc.json
  -> ReportView.get_args()
  -> Base list fetch calls frappe.desk.reportview.get
  -> reportview.get -> get_form_params -> validate_args -> execute(DatabaseQuery)
  -> compress result to {keys, values, user_info}
  -> client rebuilds rows and renders datatable/chart config
```

## 5. Saved Report Builder runtime from `Report` document

For saved builder reports, `Report.run_standard_report()` executes when the report is accessed through `Report.get_data()`. It does:

1. parse `Report.json`
2. determine columns from `fields` / `columns` config or `in_list_view` defaults
3. merge saved filters with runtime filters
4. compute order/group-by
5. run `frappe.get_list(...)`
6. build column objects from metadata
7. append totals row if configured

This is distinct from the live List/Report View runtime, which goes through `reportview.py` and `DatabaseQuery`.

## 6. Prepared report flow

```text
QueryReport.refresh()
  -> run() returns prepared_report doc or current result
  -> if user chooses Generate New Report
      -> prepared_report.make_prepared_report(report_name, filters)
      -> Prepared Report inserted with status=Queued
      -> after_insert enqueues generate_report
      -> worker generate_report() calls generate_report_result()
      -> result serialized to .json.gz File attachment
      -> status=Completed + realtime event + Notification Log
      -> user revisits report with ?prepared_report_name=<doc>
      -> query_report.run() -> get_prepared_report_result()
```

## 7. Dashboard chart runtime flow

### Report-backed chart

```text
ChartWidget.get_settings()
  -> settings.method = frappe.desk.query_report.run
ChartWidget.fetch()
  -> call run(report_name, filters, ignore_prepared_report=1)
  -> if chart_doc.use_report_chart: use result.chart.data
  -> else derive chart data from result columns/rows + x_field/y_axis config
  -> render frappe.Chart
```

### Doctype-backed chart

```text
ChartWidget.fetch()
  -> frappe.desk.doctype.dashboard_chart.dashboard_chart.get(chart_name, filters,...)
  -> backend aggregates via frappe.get_list
  -> returns {labels, datasets} or heatmap payload
  -> client renders frappe.Chart
```

## 8. Export flows

### Query report export

- client opens export dialog in `query_report.js`
- submits to `frappe.desk.query_report.export_query`
- endpoint reruns `run()` and formats CSV/XLSX
- optional background email delivery via `run_export_query_job`

### Report View export

- client submits to `frappe.desk.reportview.export_query`
- backend reruns `DatabaseQuery.execute`
- enforces export permissions per doctype/owner

## 9. Print/PDF flow for query reports

Client-only orchestration in `query_report.js`:

1. get current visible rows/columns from datatable
2. optionally fetch print format HTML
3. optionally render letterhead via `frappe.utils.print_format.render_letterhead_for_print`
4. build HTML using `print_grid` or custom report HTML format
5. either call `frappe.render_grid(...)` for print preview or `frappe.render_pdf(...)`

No dedicated report-print backend endpoint is required for standard Desk print/PDF workflow.

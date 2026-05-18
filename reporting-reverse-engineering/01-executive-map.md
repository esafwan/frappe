# Executive Map

## High-level architecture

Frappe reporting is not one feature; it is **three adjacent runtime families** sharing the `Report` DocType:

| Family | User-facing route / UI | Main backend entry | Storage nucleus |
| --- | --- | --- | --- |
| Query / Script / Custom Report | Desk route `query-report/<report_name>` via `frappe/public/js/frappe/views/reports/query_report.js` | `frappe.desk.query_report.run` | `tabReport` + optional file-backed standard report JS/Python/HTML |
| Report Builder / Report View | Desk route `List/<doctype>/Report[/<saved_report>]` via `report_view.js` | `frappe.desk.reportview.get` / `get_list` / `save_report` | `tabReport.json` for saved builder configs |
| Dashboard charts sourced from doctypes/reports/custom sources | dashboard widgets + `Dashboard Chart` form | `frappe.desk.doctype.dashboard_chart.dashboard_chart.get` or `frappe.desk.query_report.run` | `tabDashboard Chart` + child tables + optional file-backed chart source JS |

## Core files to know first

### Backend

- `frappe/core/doctype/report/report.py`
  - canonical `Report` document behavior
  - dispatches query/script/report-builder modes
- `frappe/desk/query_report.py`
  - main runtime for query/script/custom reports
  - normalizes return payload
  - exports, prepared report retrieval, filter-link permission checks
- `frappe/desk/reportview.py`
  - list/report-builder query engine and save/delete endpoints
- `frappe/core/doctype/prepared_report/prepared_report.py`
  - background generation, attachment storage, retrieval
- `frappe/desk/doctype/dashboard_chart/dashboard_chart.py`
  - dashboard chart storage validation and chart data generation
- `frappe/boot.py`
  - report visibility resolution via `get_allowed_reports()` / `get_allowed_report_names()`

### Frontend

- `frappe/public/js/frappe/views/reports/query_report.js`
  - query/script/custom report page
  - loads report JS, builds filters, calls backend, renders table/chart/summary
- `frappe/public/js/frappe/views/reports/report_view.js`
  - report-builder/list-report page
- `frappe/public/js/frappe/views/reports/report_utils.js`
  - column parsing, chart helper generation, export dialog
- `frappe/public/js/frappe/widgets/chart_widget.js`
  - dashboard widget runtime for dashboard charts, including report-backed charts
- `frappe/public/js/frappe/utils/dashboard_utils.js`
  - dashboard filter/config helpers

## Canonical report types in this tree

| `Report.report_type` | Meaning | Backend path | Storage style |
| --- | --- | --- | --- |
| `Query Report` | SQL text stored in report record; runtime runs SQL directly | `Report.execute_query_report` -> `frappe.db.sql` | DB-backed `Report.query`, optional DB child tables for columns/filters |
| `Script Report` | Python `execute(filters)` contract, file-backed for standard reports or DB-backed script for custom/non-standard | `Report.execute_script_report` | Standard: app files + `Report` row; Non-standard: `Report.report_script` and optional `Report.javascript` |
| `Custom Report` | Saved user/customized derivative of another query/script report | `frappe.desk.query_report.get_report_doc` resolves `reference_report` | DB-backed `Report.json` storing custom columns/filters |
| `Report Builder` | Saved list view/report builder definition over a DocType | `Report.run_standard_report` or `frappe.desk.reportview.*` | DB-backed `Report.json` storing fields/filters/order/grouping/chart args |

## Main runtime split

### 1. Query/Script report flow

`query_report.js` -> `frappe.desk.query_report.get_script` -> client filter config and report JS -> `frappe.desk.query_report.run` -> `generate_report_result()` -> render datatable/chart/summary.

### 2. Report Builder flow

`report_view.js` -> `frappe.desk.reportview.get` -> `DatabaseQuery.execute()` -> compressed response -> client datatable/chart widgets.

### 3. Dashboard chart flow

`chart_widget.js` ->
- for `chart_type == 'Report'`: call `frappe.desk.query_report.run`
- for doctype-backed charts: call `frappe.desk.doctype.dashboard_chart.dashboard_chart.get`
- for custom charts: load source JS via `dashboard_chart_source.get_config`, then call its configured method.

## Most important conclusions

1. **The canonical response contract for query/script/custom reports is produced in one place**: `frappe.desk.query_report.generate_report_result()`.
2. **Script reports are more powerful than query reports** because they can return not only columns/data, but also message, chart, report summary, and skip-total-row flags.
3. **Query reports are not file-backed SQL modules** in this repo version; their SQL lives in `Report.query` in the database/exported JSON.
4. **Standard script reports are dual-backed**:
   - report metadata in `tabReport`
   - executable Python/JS/HTML files inside app modules.
5. **Prepared reports are attachment-backed**: the generated result is serialized as compressed JSON (`.json.gz`) attached to `Prepared Report` records.
6. **Dashboard charts have a distinct persistence model from reports**, even when they are report-backed.
7. **Permissions are layered**:
   - report visibility by report roles / custom roles
   - ref DocType `report` permission
   - link-filter target permission checks
   - prepared report visibility derived from allowed reports.

## Reading order for the rest of this dossier

1. `02-core-doctypes-and-storage.md`
2. `03-query-reports.md`
3. `04-script-reports.md`
4. `05-report-runtime-flow.md`
5. `06-frontend-reporting-layer.md`
6. `07-backend-apis-and-methods.md`
7. `08-charting-system.md`
8. `09-prepared-reports-caching-and-background-jobs.md`
9. `10-permissions-security-and-risks.md`
10. `12-reimplementation-blueprint.md`

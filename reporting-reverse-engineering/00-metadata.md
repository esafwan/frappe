# Reporting / Charting Reverse-Engineering Metadata

## Repository metadata

| Item | Value |
| --- | --- |
| Repository path | `/workspace/frappe` |
| Primary app in tree | `frappe` |
| Frappe version | `17.0.0-dev` from `frappe/__init__.py` |
| Frappe develop version marker | `17.x.x-develop` from `frappe/hooks.py` |
| ERPNext presence in this checkout | Not present (`erpnext/` directory absent) |
| Current git branch | `work` |
| Current commit SHA | `eb80cb679699c570aa77a9e017a008e3dd8e8084` |
| Working tree state at analysis start | Clean (`git status --short` returned no entries) |
| Analysis timestamp (UTC) | `2026-03-23T03:37:50Z` |
| Network/runtime execution used | Static source inspection only; no app boot, no tests, no DB-backed runtime verification |

## App / package metadata detected

- `frappe/hooks.py`
  - `app_name = "frappe"`
  - `app_title = "Frappe Framework"`
- `frappe/__init__.py`
  - `__version__ = "17.0.0-dev"`
- `pyproject.toml`
  - package name `frappe`

## Scope actually analyzed

This dossier covers the reporting and charting stack present in this repo:

- **Core report model**: `Report`, `Report Filter`, `Report Column`
- **Report execution**: `frappe.core.doctype.report.report`, `frappe.desk.query_report`, `frappe.desk.reportview`
- **Prepared reports**: `Prepared Report` DocType and workers
- **Charting**:
  - `Dashboard Chart`
  - `Dashboard Chart Field`
  - `Dashboard Chart Source`
  - chart widgets and dashboard utilities
- **Adjacent analytics constructs**:
  - Number Cards where they overlap report/chart UX
  - Auto Email Report integrations that call report APIs
- **Example reports shipped in Frappe core**

## Important caveats

1. **Static-only analysis**: all findings are derived from source files, DocType JSON, and tests. No live DB or Desk runtime was started.
2. **No ERPNext source present**: ERPNext-specific examples requested by the prompt could not be extracted from this checkout. Section 11 therefore documents the gap explicitly and uses Frappe core reports as representative examples.
3. **Version sensitivity**: these findings are tied to the checked-out Frappe `17.0.0-dev` tree and commit `eb80cb679699c570aa77a9e017a008e3dd8e8084`.
4. **Line numbers omitted on purpose**: paths, symbols, and call chains are given so another agent can locate source without requiring exact line stability across nearby commits.
5. **“Report” means multiple subsystems** in Frappe:
   - SQL/script/query reports routed through `frappe.desk.query_report`
   - list/report-builder views routed through `frappe.desk.reportview`
   - dashboard charts and cards that can be sourced from reports

## Analysis method

1. Captured repo metadata from `git`, `pyproject.toml`, `frappe/__init__.py`, and `frappe/hooks.py`.
2. Enumerated report/chart-related files with repo-wide ripgrep searches for:
   - `Query Report`
   - `Script Report`
   - `Report Builder`
   - `Prepared Report`
   - `Dashboard Chart`
   - report runtime methods such as `run`, `get_script`, `execute`, `get`
3. Traced backend execution starting from:
   - `frappe.desk.query_report.run`
   - `frappe.core.doctype.report.report.Report.get_data`
   - `frappe.desk.reportview.get`
   - `frappe.core.doctype.prepared_report.prepared_report.generate_report`
   - `frappe.desk.doctype.dashboard_chart.dashboard_chart.get`
4. Traced frontend entry points from:
   - `frappe/public/js/frappe/views/reports/query_report.js`
   - `frappe/public/js/frappe/views/reports/report_view.js`
   - `frappe/public/js/frappe/widgets/chart_widget.js`
   - `frappe/public/js/frappe/views/dashboard/dashboard_view.js`
5. Inspected DocType JSON definitions for storage contracts.
6. Used shipped tests and boilerplates as executable/spec evidence for contracts.

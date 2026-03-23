# ERPNext Examples and Patterns

## Repository reality in this analysis

The checked-out repository at `/workspace/frappe` does **not** contain an `erpnext/` app tree.

Therefore:

- no ERPNext reports could be inspected directly
- no ERPNext chart definitions could be traced in source
- no ERPNext-specific conventions can be proven from this checkout

## What can still be said reliably

Frappe’s packaging/runtime conventions strongly imply how ERPNext reports would work, because ERPNext reports are implemented on top of the same `Report` DocType and runtime APIs.

Conventions likely shared by ERPNext, based on Frappe core evidence:

1. standard script reports live under `<app>/<module>/report/<report_name>/`
2. report JS config registers `frappe.query_reports[report_name]`
3. `execute(filters)` is the Python entry point
4. advanced reports can return `chart` and `report_summary`
5. dashboard charts can either consume report-returned chart data or derive from tabular report rows

## Frappe-core examples that stand in as representative patterns

### Pattern: standard script report with helper actions

Example:
- `frappe/core/report/database_storage_usage_by_tables/database_storage_usage_by_tables.py`
- paired JS: `.../database_storage_usage_by_tables.js`

Why it matters:

- demonstrates standard file-backed script report packaging
- shows `execute(filters)` plus extra whitelisted helper (`optimize_doctype`)
- shows report JS adding action buttons through `report.page.add_inner_button(...)`

### Pattern: script report with dynamic filter query

Example:
- `frappe/core/report/permitted_documents_for_user/permitted_documents_for_user.py`
- paired JS: `.../permitted_documents_for_user.js`

Why it matters:

- shows report JS filter definitions
- shows filter `get_query` calling another whitelisted Python function in same report module
- shows string-based column definitions like `Name:Link/User:200`

### Pattern: report builder persisted in `Report.json`

Examples:
- `frappe/core/doctype/report/user_activity_report.json`
- `.../user_activity_report_without_sort.json`

Why it matters:

- shows actual serialized report-builder schema
- proves builder reports are stored as JSON on Report docs, not as a separate definition table

## Representative patterns another agent can expect in ERPNext

If ERPNext source is later available, likely good examples to inspect would be:

1. financial statement script reports
   - to study `report_summary`, `chart`, total-row suppression, tree rows
2. stock/ledger reports
   - to study prepared-report heavy usage and long-running patterns
3. sales analytics reports
   - to study dashboard/report chart coupling
4. operational query reports
   - to study SQL string column conventions and filter JS patterns

## Verification gap

Because ERPNext is absent, this section should be treated as:

- **architecture inference from Frappe core** for conventions
- **not direct ERPNext evidence**

Any implementation intended to match ERPNext behavior should perform a second pass on an ERPNext checkout before finalizing assumptions about:

- report return shapes used in practice
- chart payload conventions in analytics-heavy modules
- prepared-report adoption patterns
- ERPNext-specific helper APIs adjacent to report modules

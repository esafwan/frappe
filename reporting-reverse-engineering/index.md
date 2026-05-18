# Reporting / Charting Reverse-Engineering Index

## Table of contents

1. [00-metadata.md](./00-metadata.md)
2. [01-executive-map.md](./01-executive-map.md)
3. [02-core-doctypes-and-storage.md](./02-core-doctypes-and-storage.md)
4. [03-query-reports.md](./03-query-reports.md)
5. [04-script-reports.md](./04-script-reports.md)
6. [05-report-runtime-flow.md](./05-report-runtime-flow.md)
7. [06-frontend-reporting-layer.md](./06-frontend-reporting-layer.md)
8. [07-backend-apis-and-methods.md](./07-backend-apis-and-methods.md)
9. [08-charting-system.md](./08-charting-system.md)
10. [09-prepared-reports-caching-and-background-jobs.md](./09-prepared-reports-caching-and-background-jobs.md)
11. [10-permissions-security-and-risks.md](./10-permissions-security-and-risks.md)
12. [11-erpnext-examples-and-patterns.md](./11-erpnext-examples-and-patterns.md)
13. [12-reimplementation-blueprint.md](./12-reimplementation-blueprint.md)
14. [13-open-questions-and-verification-gaps.md](./13-open-questions-and-verification-gaps.md)

## Key conclusions

- Frappe has four persisted report types in `Report.report_type`: `Report Builder`, `Query Report`, `Script Report`, `Custom Report`.
- The canonical query/script/custom execution API is `frappe.desk.query_report.run`.
- The canonical response contract is assembled by `frappe.desk.query_report.generate_report_result()`.
- Query report SQL lives in `Report.query`; script report Python lives either in app files (standard) or `Report.report_script` (non-standard).
- Report Builder persistence lives in `Report.json` and live execution is closely related to `frappe.desk.reportview` and `DatabaseQuery`.
- Prepared reports store metadata in `tabPrepared Report` and result payloads as attached compressed JSON files.
- Dashboard charts are a separate persistence/runtime system and can be backed by doctypes, reports, or custom source JS.
- Permission enforcement is layered: report roles, custom roles, ref-doctype report permission, row filtering, link-filter checks, prepared/chart access rules.
- For external UI/API work, the safest compatibility approach is to wrap `get_script`, `run`, prepared-report APIs, and dashboard chart APIs behind a normalized façade.
- For AI-driven authoring, Report Builder and derived chart configs are the safest primitives; raw SQL, Python, JS, and dynamic filter expressions require strong review controls.

## Recommended reading order

If you need only the operational mental model:

1. `01-executive-map.md`
2. `05-report-runtime-flow.md`
3. `07-backend-apis-and-methods.md`
4. `08-charting-system.md`
5. `12-reimplementation-blueprint.md`

If you need implementation-level fidelity:

Read all files in numeric order.

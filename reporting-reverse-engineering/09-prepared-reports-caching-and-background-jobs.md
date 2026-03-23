# Prepared Reports, Caching, and Background Jobs

## Purpose

Prepared reports offload expensive report execution to background jobs and persist the result for later retrieval.

Main files:

- `frappe/core/doctype/prepared_report/prepared_report.py`
- `frappe/core/doctype/prepared_report/prepared_report.json`
- `frappe/desk/query_report.py`
- `frappe/core/doctype/role_permission_for_page_and_report/role_permission_for_page_and_report.py`

## When prepared report mode is used

### Explicitly enabled reports

If `Report.prepared_report` is true, `frappe.desk.query_report.run()` prefers `get_prepared_report_result()` unless:

- `ignore_prepared_report` is true, or
- `custom_columns` were requested

### Slow script reports auto-enable it

`Report.execute_script_report()` starts a 15-second timer. If the report has not finished before the timer fires, `enable_prepared_report(report, site)` sets `Report.prepared_report = 1` in the database.

This means prepared report mode can become a persistent operational optimization after a slow live run.

### Admin role control UI

Single DocType `Role Permission for Page and Report` exposes `enable_prepared_report` for a report and directly updates `tabReport.prepared_report`.

## Job lifecycle

### Creation

API: `make_prepared_report(report_name, filters)`

- canonicalizes filter JSON with `process_filters_for_prepared_report`
- inserts `Prepared Report`
- `before_insert` sets `status = 'Queued'`
- `after_insert` enqueues `generate_report` on `long` queue

### Worker execution

`generate_report(prepared_report)`:

1. `update_job_id()` -> stores RQ job id and marks `Started`
2. load target report
3. resolve custom report custom columns if needed
4. call `generate_report_result(report, filters, user)`
5. `create_json_gz_file(...)`
6. mark `Completed`
7. create `Notification Log`
8. set `report_end_time`, `peak_memory_usage`
9. publish realtime `report_generated`

### Failure handling

- any exception leads to `_save_error(instance, traceback)`
- record marked `Error`
- error text stored in `error_message`

### Timeout behavior

- default timeout constant: `REPORT_TIMEOUT = 25 * 60`
- per-report override: `Report.timeout`
- stalled started jobs older than `FAILURE_THRESHOLD = 6h` can be marked failed by `expire_stalled_report()`

## Filter canonicalization

`process_filters_for_prepared_report(filters)` serializes filters with:

- sorted keys (`frappe.as_json` behavior)
- no indentation
- compact separators `(',', ':')`

Reason: exact string equality is used to match queued/completed prepared reports. Without canonical serialization, semantically identical filters with different spacing/order would not dedupe.

## Result serialization format

Function: `create_json_gz_file(data, dt, dn, report_name)`

### Stored artifact

- compressed gzip payload
- content is `frappe.as_json(data, indent=None, separators=(',', ':'))`
- saved as private `File`
- filename pattern: `<scrubbed_report_name>_<timestamp>.json.gz`
- attached to doctype/name of prepared report record

### Retrieval

`PreparedReport.get_prepared_data(with_file_name=False)`:

- locates attached `.gz` file
- reads `File` content
- gzip-decompresses it
- returns bytes (and filename if requested)

### Legacy compatibility

`get_prepared_report_result()` supports older stored formats where columns might be stored separately or result payload might be a list rather than dict.

## User retrieval paths

### From report page

- route query string may include `prepared_report_name`
- `query_report.run()` reads the specific prepared report or finds latest completed matching one
- response includes `prepared_report: True` and `doc`
- client disables filters when viewing a specific prepared report snapshot

### Direct download

API: `download_attachment(dn)`

- checks prepared report read permission
- returns decompressed JSON file as binary response

### CSV conversion

API: `enqueue_json_to_csv_conversion(prepared_report_name)`

- background job converts stored JSON to CSV
- attaches CSV file to same `Prepared Report`
- notifies user via `Notification Log`

## Permission model

Prepared report permission is not purely ownership-based.

### Query condition / read access

`prepared_report.get_permission_query_condition(user)` and `has_permission(doc, user)` allow access if:

- user is Administrator, or
- user has System Manager role, or
- `doc.report_name` is in `UserPermissions(user).get_all_reports()`

This couples prepared report access to **current report visibility rules**, not only ownership.

## Caching

### Execution time cache

- query/script runtime stores execution time in Redis hash `report_execution_time`
- `get_script()` and `run()` include it in response
- client uses it to decide whether to show a “Preparing Report” progress bar

### Dashboard chart cache

Separate from prepared reports: `dashboard_chart.get` is decorated with `@cache_source`, which caches chart source results.

## Design implications for custom UI / API

1. Prepared reports should be treated as **snapshot artifacts**, not just async jobs.
2. External systems should preserve canonical filter serialization if they want dedupe behavior compatible with Frappe.
3. For large results, the cleanest interoperability path is:
   - request prepared report creation
   - poll/list `Prepared Report`
   - download compressed JSON attachment
4. Because prepared reports can be auto-enabled after slow executions, an external UI should not assume a report is always synchronously runnable.

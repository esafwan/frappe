# Open Questions and Verification Gaps

## Confidence legend

- **High**: directly proven from current source and/or tests
- **Medium**: strongly implied by source, but not runtime-verified here
- **Low**: architectural inference requiring live verification

## Open items

### 1. Exact safe SQL restrictions

- **Confidence**: Medium
- Evidence: `Report.execute_query_report()` calls `check_safe_sql_query(self.query)`.
- Gap: validator implementation and exact forbidden SQL surface were not expanded in this pass.
- Why it matters: external SQL-generation policy depends on its boundaries.

### 2. Full `safe_exec` capability surface for DB script reports

- **Confidence**: Medium
- Evidence: non-standard script reports run through `safe_exec(report_script, ...)`.
- Gap: this dossier did not enumerate the entire sandbox capability model from `safe_exec` internals.
- Why it matters: AI/code-generation safety policy.

### 3. Full set of report JS hooks used in the ecosystem

- **Confidence**: Medium
- Evidence: `query_report.js` references several hooks (`onload`, `formatter`, etc.).
- Gap: other hooks may exist conventionally in app code not present in this repo.
- Why it matters: a complete external compatibility layer may need more hooks.

### 4. Runtime behavior of some report summary item shapes

- **Confidence**: Medium
- Evidence: client renders via `frappe.utils.build_summary_item`, but this pass did not inspect all summary item fields.
- Why it matters: exact schema normalization for custom UI cards.

### 5. ERPNext real-world conventions

- **Confidence**: Low for ERPNext-specific claims
- Evidence: ERPNext source absent.
- Why it matters: financial reports and stock analytics in ERPNext often stress advanced script report features.

### 6. Backward compatibility edge cases in prepared report payloads

- **Confidence**: Medium
- Evidence: `get_prepared_report_result()` contains backward-compatibility branches.
- Gap: older payload variants were not reproduced or sampled.

### 7. How often `Report.get_data()` is used by external callers vs route APIs

- **Confidence**: Medium
- Evidence: code and tests use it; Desk primarily uses `query_report.run` and `reportview.get`.
- Why it matters: if building library-style integrations, `Report.get_data()` may be useful but lacks some outer-layer checks.

## Runtime verification recommended later

1. Start a dev site and capture actual JSON from:
   - a query report
   - a standard script report with chart + summary
   - a custom report
   - a prepared report retrieval
2. Inspect exact `safe_sql_query` rejection examples.
3. Inspect `safe_exec` available globals and disallowed operations.
4. Verify how custom print HTML interacts with PDF generation for reports.
5. Verify report/chart behavior under restricted user permissions and shared-doc scenarios.
6. Repeat this study on an ERPNext checkout to capture real-world heavy reports.

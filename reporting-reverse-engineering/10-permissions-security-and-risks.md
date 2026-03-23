# Permissions, Security, and Risks

## Permission layers for running a report

A user must pass **multiple gates**.

## 1. Report visibility by report roles

### Standard role rows

`Report.roles` child rows (`Has Role`) are checked by:

- `Report.is_permitted()` at runtime
- `frappe.boot.get_allowed_reports()` when building boot info and allowed report maps

If no roles are configured, report is effectively open to anyone who can also satisfy lower-layer doctype permissions.

### Custom role overrides

The single DocType UI `Role Permission for Page and Report` writes to `Custom Role` docs. `get_allowed_reports()` first loads custom roles; if a report has custom-role rows, they override the report’s standard role list.

## 2. Ref DocType report permission

Even if report visibility passes, `get_report_doc()` additionally requires:

```python
frappe.has_permission(report.ref_doctype, "report")
```

This is a critical second gate. A visible report does not run unless the user has report permission on the referenced DocType.

## 3. Row-level filtering after execution

`generate_report_result()` calls `get_filtered_data(report.ref_doctype, columns, result, user)`.

Observed behavior includes:

- building linked-doctype maps from report columns/results
- obtaining match conditions via `reportview.build_match_conditions`
- honoring shared documents
- applying field masking for masked fields
- filtering out rows that violate user match filters

Implication: even if a report query/script returns more data, the final rows returned to the client are still filtered post-execution in many cases.

## 4. Filter target permission checks

`validate_filters_permissions()` checks that a user can `read` or `select` the specific documents referenced by Link filter values.

This matters for custom UIs because a malicious caller could otherwise test for existence of forbidden linked records by passing them as filters.

## 5. Prepared report access

Prepared report access is derived from `UserPermissions.get_all_reports()`, meaning a user can read prepared reports only for reports they are currently allowed to access, with administrator/system-manager exceptions.

## 6. Dashboard chart access

### Query conditions

`dashboard_chart.get_permission_query_conditions()` restricts charts based on:

- allowed source doctypes for doctype-backed charts
- allowed reports for report-backed charts
- allowed modules for the user

### Per-doc access

`dashboard_chart.has_permission()` allows if:

- System Manager
- role whitelist on chart intersects user roles
- or user can access referenced report / doctype

## Security risks by mechanism

## Query Reports

### Strengths

- SQL is passed through `check_safe_sql_query`
- link filters are permission-checked
- final rows are permission-filtered again

### Risks

- SQL remains fundamentally powerful and hard to review automatically
- safe-SQL validator quality becomes a single critical trust boundary
- LLM-generated SQL is high-risk unless heavily constrained and reviewed

## Script Reports

### Strengths

- standard script reports are auditable source files
- DB scripts execute through `safe_exec`, not raw unrestricted `exec`

### Risks

- non-standard DB script reports still represent code execution surface
- adjacent whitelisted helper methods in script report modules may expose extra mutation power
- AI-generated Python here is materially riskier than AI-generated builder configs

## Report Builder

### Strengths

- based on `DatabaseQuery` and DocType metadata
- field/filter validation is strong relative to raw SQL
- easiest report type to expose to AI safely

### Risks

- still tied to Desk-centric JSON schema and list-view semantics
- custom column additions can traverse linked doctypes and broaden exposure if not revalidated externally

## Custom Reports

### Risks

- custom reports inherit execution from base report but can persist arbitrary filters/column overlays
- naming and ownership control are important if exposing save endpoints to untrusted callers

## Dashboard chart dynamic filters

### Major risk

`dashboard_utils.get_all_filters()` uses `eval()` client-side on `dynamic_filters_json` expressions.

This is acceptable only in trusted-admin configuration workflows. It is **not AI-safe** to let LLMs emit arbitrary dynamic filter expressions.

## Prepared reports

### Risks

- stored snapshots can outlive permission changes if access controls around the `Prepared Report` doc are misapplied elsewhere
- result attachment may contain sensitive data at time of generation
- external systems should consider retention and invalidation policies

## AI-facing attack surfaces

1. generating SQL into `Report.query`
2. generating Python into `Report.report_script`
3. generating JS into `Report.javascript`
4. generating `Dashboard Chart Source` JS
5. generating `dynamic_filters_json` expressions evaluated by browser `eval`
6. invoking helper methods adjacent to report modules that mutate data

## Recommended safe AI exposure tiers

### Tier 1: safe

Allow AI to create/edit:

- Report Builder configs
- Custom report column/filter presets
- Dashboard charts derived from existing approved reports
- Number cards over existing approved reports/doctypes

### Tier 2: guarded

Allow AI to propose but not auto-apply:

- Query report SQL
- report filter schemas
- chart custom options

### Tier 3: human-review-only

Never auto-apply without review:

- `report_script`
- `javascript`
- `Dashboard Chart Source` JS
- `dynamic_filters_json` expressions

## Minimum validation for an external API layer

Any external reporting API should:

1. use `frappe.desk.query_report.run` rather than bypassing it
2. preserve `validate_filters_permissions` behavior
3. require explicit allowlists for mutable report types
4. reject arbitrary code-bearing fields by default
5. separate “draft/proposal” from “published runnable report” states

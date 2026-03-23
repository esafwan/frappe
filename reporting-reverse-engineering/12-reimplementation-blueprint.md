# Reimplementation Blueprint

## Goal

Reproduce Frappe reporting behavior outside Desk, ideally in a custom React UI and in AI-assisted workflows, without depending on source access at runtime.

## Recommended abstraction model

Split the system into five normalized resource types.

## 1. `ReportDefinition`

```json
{
  "name": "Permitted Documents For User",
  "report_type": "Script Report",
  "ref_doctype": "User",
  "is_standard": true,
  "execution_mode": "script_module",
  "prepared_report_enabled": false,
  "disabled": false,
  "filter_schema": [...],
  "column_schema": [...],
  "client_features": {
    "formatter": true,
    "chart_hook": false,
    "tree": false,
    "custom_print_html": false
  }
}
```

## 2. `ReportRunRequest`

```json
{
  "report_name": "...",
  "filters": {...},
  "ignore_prepared_report": false,
  "custom_columns": [],
  "skip_total_calculation": false
}
```

## 3. `ReportRunResult`

Mirror `frappe.desk.query_report.run`:

```json
{
  "columns": [...],
  "result": [...],
  "message": null,
  "chart": null,
  "report_summary": null,
  "skip_total_row": 0,
  "execution_time": 0.42,
  "add_total_row": true,
  "prepared_report": false
}
```

## 4. `ChartDefinition`

Normalize dashboard charts separately from reports:

```json
{
  "name": "...",
  "source_type": "report|doctype|custom_source",
  "report_name": "...",
  "document_type": "...",
  "use_report_chart": true,
  "x_field": "...",
  "y_fields": [...],
  "filters": {...},
  "dynamic_filters": [...],
  "presentation": {...}
}
```

## 5. `PreparedReportArtifact`

```json
{
  "name": "...",
  "report_name": "...",
  "filters": {...},
  "status": "Completed",
  "completed_at": "...",
  "download_url": "..."
}
```

## Custom React UI strategy

## A. Metadata bootstrap

For compatibility-first UI:

1. fetch `Report` doc metadata (or a normalized server-side wrapper)
2. call `frappe.desk.query_report.get_script`
3. parse/evaluate or server-normalize report filter schema and client features

Recommended improvement over Desk:

- build a backend adapter that converts JS/DB filter metadata into a **pure JSON schema** for React, instead of evaling JS in browser.

## B. Execution path

Use `frappe.desk.query_report.run` as the primary execution API.

Why:

- preserves permission checks
- preserves custom report overlays
- preserves totals/chart/summary contract
- preserves prepared-report fallback behavior

## C. Table rendering

Map Frappe report columns to your own grid schema:

| Frappe field | React grid equivalent |
| --- | --- |
| `fieldname` | column id |
| `label` | header |
| `fieldtype` | formatter type |
| `options` | link/currency context |
| `width` | width hint |
| `hidden` | hidden state |

Support row dicts, tree `indent`, total-row semantics, and visible-row-aware export.

## D. Chart rendering

Support both:

1. server-provided chart payload (`result.chart`)
2. local derivation from rows/columns using saved `x_field` / `y_fields`

This mirrors Frappe’s dual chart model and avoids overcoupling to one pattern.

## Cleaner API layer recommendation

Introduce your own stable façade endpoints, e.g.:

- `GET /reports/:name/metadata`
- `POST /reports/:name/run`
- `POST /reports/:name/export`
- `POST /reports/:name/prepared`
- `GET /prepared-reports/:id`
- `GET /charts/:name`

Internally, these can call Frappe whitelisted methods while shielding clients from legacy params and JS-coupled contracts.

## AI-safe report creation strategy

## Safest report type for AI generation: Report Builder

Minimum metadata an LLM must generate:

- `report_name`
- `ref_doctype`
- selected fields
- filters
- order by
- group by (optional)
- chart args (optional)

This can be validated structurally without executing arbitrary code.

## Query report generation strategy

Instead of “LLM writes SQL directly”, use:

1. LLM outputs structured intent:
   - base doctype(s)
   - selected fields
   - filters
   - aggregates
   - grouping
2. backend compiler generates SQL or DatabaseQuery form
3. validate via safe SQL checks
4. require review before publish

## Script report generation strategy

Treat script reports as a controlled compilation target only.

Recommended primitive set for an AI assistant:

- declare filter schema
- declare output columns
- choose data source template (`doctype query`, `aggregation`, `pivot`, `tree`, `comparison`)
- choose optional chart schema
- backend fills a vetted Python template
- human reviewer approves generated code

## What an LLM should never be allowed to mutate directly

- `Report.report_script`
- `Report.javascript`
- `Dashboard Chart Source` JS
- `dynamic_filters_json`

## Structured external persistence model

If you want to decouple from Desk and source-tree access, store a normalized copy of each approved report/chart definition in your own system:

- canonical report metadata
- normalized filter schema
- normalized column schema
- saved chart config
- execution mode
- prepared-report support flag
- source hashes / sync timestamps

This lets your custom UI and AI agents operate without loading raw Frappe source code.

## Stable vs brittle parts of current Frappe design

### Relatively stable

- `Report` DocType existence and core fields
- `frappe.desk.query_report.run` response shape
- script report `execute(filters)` convention
- dashboard chart persistence model
- prepared report attachment-based persistence

### Brittle / Desk-coupled

- client JS hooks stored in report JS
- filter definitions that require JS evaluation
- `dynamic_filters_json` using browser `eval`
- Report Builder JSON schema in `Report.json`
- custom report overlays piggybacking on report page assumptions

## Minimum interoperability layer to build now

If implementing a custom reporting platform over Frappe, the highest-value initial layer is:

1. metadata normalizer over `Report` and `Dashboard Chart`
2. trusted executor proxy over `query_report.run`
3. prepared-report manager
4. export proxy
5. chart normalizer that outputs one chart schema for all report/chart types
6. mutation service limited to builder/custom-report/chart presets only

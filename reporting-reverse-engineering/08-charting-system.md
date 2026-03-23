# Charting System

## Chart systems present in this repo

There are **three distinct chart-generation patterns**:

1. **Inline report charts**
   - chart payload returned as part of report response (`data.chart`)
2. **Derived report charts**
   - dashboard/report page derives chart from tabular report result using chosen x/y fields
3. **Dashboard Chart documents**
   - persisted widgets whose data comes from a DocType aggregation, a report, or a custom chart source

## A. Inline report charts

### Where produced

By script reports returning a `chart` object as the 4th return value.

Evidence:

- `frappe.desk.query_report.generate_report_result()` unpacks `chart`
- `query_report.js` prefers `data.chart` if report JS does not override with `get_chart_data`

### Expected structure

Client expects something like:

```json
{
  "data": {
    "labels": ["A", "B"],
    "datasets": [{"name": "Series", "values": [1, 2]}]
  },
  "type": "bar",
  "fieldtype": "Currency",
  "options": "currency_field_or_doctype"
}
```

Client augments it with:

- axis number formatting
- tooltip formatting based on `fieldtype` / `options`
- fixed height `280`

## B. Derived report charts on query report page

### Where configured

Client-only dialog in `query_report.js` (`open_create_chart_dialog`).

### How derived

- inspect report columns and first row values
- classify fields into numeric vs non-numeric using `report_utils.get_field_options_from_report`
- user chooses `x_field`, `y_axis_fields`, and chart type
- `report_utils.make_chart_options(columns, raw_data, values)` builds Frappe Charts data

### Persistence

This derived chart is not automatically stored unless the user chooses **Add Chart to Dashboard**.

## C. Dashboard Chart DocType system

## Chart types supported by `Dashboard Chart.chart_type`

| `chart_type` | Data source |
| --- | --- |
| `Count` | doctype-backed aggregation over time or heatmap |
| `Sum` | doctype-backed aggregation over field |
| `Average` | doctype-backed average over field |
| `Group By` | grouped categorical aggregation |
| `Report` | report-backed widget |
| `Custom` | custom chart source JS + whitelisted method |

## Visual chart types supported by `Dashboard Chart.type`

| `type` | Notes |
| --- | --- |
| `Line` | standard timeseries/category |
| `Bar` | standard |
| `Percentage` | circular/percentage chart |
| `Pie` | circular |
| `Donut` | circular |
| `Heatmap` | special calendar-like timeseries |

## Dashboard chart storage format

### Static filters

`filters_json` stores either:

- doctype filter array syntax, or
- report filter key/value mapping for report-backed charts

### Dynamic filters

`dynamic_filters_json` stores expressions that are evaluated client-side in `dashboard_utils.get_all_filters()`.

Important risk: it literally uses `eval(...)` on the expression string in browser context.

### Report-backed chart fields

- `report_name`
- `use_report_chart`
- if `use_report_chart = 0`:
  - `x_field`
  - child rows in `y_axis` with `y_field`, `color`

## Backend chart generation for doctype-backed charts

### Time series charts

Function: `get_chart_config(chart, filters, timespan, timegrain, from_date, to_date)`

Behavior:

- compute date bounds
- add datefield range filters
- query `frappe.get_list` grouped by date field
- aggregate with `SUM(value_field)` and `COUNT(*)`
- post-process into regular buckets via `get_result(...)`
- return:

```python
{
  "labels": [...period labels...],
  "datasets": [{"name": _(chart.name), "values": [...]}],
}
```

### Heatmap charts

Function: `get_heatmap_chart_config`

Returns:

```python
{
  "labels": [],
  "dataPoints": {unix_timestamp_or_epoch: aggregated_value, ...}
}
```

Client later injects `data.start` and `data.end` based on chosen year.

### Group By charts

Function: `get_group_by_chart_config`

Returns:

```python
{
  "labels": [group labels],
  "datasets": [{"name": _(chart.name), "values": [counts_or_aggregates]}],
}
```

If grouped field is a `Link`, backend attempts to replace names with linked doctype title-field values.

## Report-backed dashboard charts

### Runtime behavior

`chart_widget.js` calls `frappe.desk.query_report.run(report_name, filters, ignore_prepared_report=1)`.

Then:

- if chart doc says `use_report_chart`, widget consumes `result.chart.data`
- else widget computes chart data from rows/columns using the saved `x_field` and `y_axis`

### Contract implications

A report intended for reuse as dashboard widget can support either:

1. **self-contained chart mode**: return `chart` from script report
2. **tabular-to-chart mode**: just return columns/result; dashboard chart doc chooses axes externally

## Custom chart sources

### Storage and load

- metadata stored in `Dashboard Chart Source`
- JS code loaded via `dashboard_chart_source.get_config(name)`
- JS must register `frappe.dashboards.chart_sources[source_name]`

### Expected custom source shape

Inferred from widget code:

- object available at `frappe.dashboards.chart_sources[source]`
- should include at least:
  - `method` (backend method to call for data)
  - optional `filters`

Because the widget treats it similarly to report source config and calls `this.settings.method`.

## Rendering component

All chart variants ultimately render using `frappe.Chart` / `frappe.utils.make_chart` on the client.

Important client enrichment in `ChartWidget.get_chart_args()`:

- maps `Line/Bar/Percentage/Pie/Donut/Heatmap` to chart library types
- injects tooltip formatting based on currency, fieldtype, or report chart fieldtype
- merges user-specific chart config and `custom_options`
- supports `show_values_over_chart`

## Dashboard user-specific configuration

User-specific chart settings are saved through:

- `frappe.desk.doctype.dashboard_settings.dashboard_settings.save_chart_config`

Used for:

- selected filters
- timespan
- time interval
- date range
- heatmap year

These settings are distinct from `Dashboard Chart` document defaults.

## How charts connect to reports

There is no separate “Report Chart” table. The linkage is encoded in `Dashboard Chart` rows where `chart_type = 'Report'` and `report_name = <Report>`.

Two patterns:

1. **reuse report-provided chart**: `use_report_chart = 1`
2. **derive chart from report columns**: `use_report_chart = 0`, plus saved `x_field` + `y_axis`

This split is crucial for custom UI design because it means the external system can represent report charting as either:

- embedded chart contract from report execution, or
- separate chart config over a tabular result set.

# Search in Frappe (Current Architecture + Extensible Backends Plan)

This folder documents:

- **How search works today in Frappe Framework** (what gets indexed, where the index lives, and how queries are executed).
- **A master plan for adding pluggable search backends via an external app** (starting with MariaDB full-text search, but designed to support future backends).

## Contents

- [`current-search.md`](./current-search.md): Current implementation details (indexing + retrieval) for:
  - Desk **Global Search** (`frappe.utils.global_search`)
  - Website search (`frappe.search.web_search`, backed by Whoosh)
  - App-provided SQLite FTS framework (`frappe.search.sqlite_search`)
- [`pluggable-backends-plan.md`](./pluggable-backends-plan.md): Proposed architecture for a separate app that can provide alternative search backends and routing.


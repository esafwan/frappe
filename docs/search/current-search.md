# Current search implementation in Frappe Framework

Frappe currently ships **multiple search subsystems** that serve different UX surfaces:

- **Desk Global Search**: the omnibox search in Desk, backed by the `__global_search` table and the database’s native text search primitives.
- **Website Search**: the website header search box, backed by a Whoosh index built from rendered web routes.
- **SQLite Search Framework**: a pluggable FTS5-based framework intended for app-level search experiences (with scoring, highlighting, spelling correction, and permission-aware filtering).

This doc explains **what is indexed**, **where it is stored**, and **how retrieval works** for each.

---

## 1) Desk Global Search (`frappe.utils.global_search`)

### What it is

Desk Global Search is implemented in `frappe/utils/global_search.py` and powers the Desk search UI (`frappe/public/js/frappe/ui/toolbar/search_utils.js`).

It indexes document “searchable fields” (DocFields marked to be included in global search) into a single logical corpus stored in a table called `__global_search`.

### Storage and engine

`__global_search` is created by `frappe.db.create_global_search_table()` with different physical implementations per database:

- **MariaDB**: a real table with a `FULLTEXT(content)` index, using `ENGINE=MyISAM` (`frappe/database/mariadb/database.py`).
- **Postgres**: a normal table without a native index definition in schema; queries use `TO_TSVECTOR(...) @@ ...` in some paths (see “Web Search” below).
- **SQLite**: a `FTS5` virtual table (`frappe/database/sqlite/database.py`).

### Index contents (what gets stored)

Each indexed row contains:

- `doctype`: the document type
- `name`: the document name
- `title`: document title (best-effort)
- `content`: concatenated “global search” field values
- `route`: website route (when applicable)
- `published`: website-published flag (when applicable)

Field values are formatted as `"<Label> : <value>"` and concatenated with a delimiter (`" ||| "`).

Text-ish fields (`Text`, `Text Editor`) are normalized:

- scripts/styles removed
- HTML stripped
- whitespace normalized

### How documents are selected for indexing

Global search relies on DocType metadata:

- `frappe.get_meta(doctype).get_global_search_fields()` returns fields configured to be indexed.
- Child tables are included: parent DocType table fields are inspected; child DocTypes with global search fields contribute their indexed content.

Documents are **skipped** if:

- `docstatus == 2` (cancelled)
- the DocType has `enabled/disabled` fields and the record is disabled

### How indexing updates happen (incremental)

Global Search updates are wired into the core document lifecycle:

- On every successful save/update, `Document.run_post_save_methods()` calls `update_global_search(self)` (`frappe/model/document.py`).
- On delete, `delete_for_document(doc)` runs (`frappe/model/delete_doc.py`).

`update_global_search(doc)` extracts indexable values and pushes them to a Redis-backed queue:

- Key: `global_search_queue`
- Data: JSON of `{doctype, name, content, published, title, route}`

To avoid write-amplification, the queue is periodically drained and de-duplicated:

- `sync_global_search()` pops queue items, de-dupes by `(doctype, name)`, and upserts into `__global_search`.
- If Redis is unavailable, indexing falls back to a synchronous upsert (`sync_value(...)`).

### How indexing rebuilds happen (full rebuild)

Full rebuild is handled per-DocType:

- `rebuild_for_doctype(doctype)` deletes all rows for that doctype and re-inserts from the DocType table (plus child tables).
- This is used when “global search fields” change.

### How retrieval works (querying)

Primary API:

- `frappe.utils.global_search.search(text, start=0, limit=20, doctype="")`
- Desk UI calls this via `frappe.call({ method: "frappe.utils.global_search.search", ... })`.

Key behaviors:

- **Doctype gating (permission + config)**:
  - Allowed doctypes = `Global Search Settings` configured doctypes ∩ user `can_read`.
  - There is **no row-level permission filtering** here; it is doctype-level gating.
- **Tokenization**:
  - Input is split on `&` and each token is searched separately; results are accumulated.
- **Ranking**:
  - Query Builder uses `Match(...).Against(word)` to compute a `rank`, and results are ordered by rank descending.
  - The final list is re-ordered by configured doctype priority (`Global Search Settings`) and filtered to `rank > 0.0`.
- **Enrichment**:
  - For doctypes with `title_field` / `image_field`, values are fetched per-row to enrich results.

Return shape (simplified):

- `doctype`, `name`, `content`, `rank`
- optionally `title`, `image`

### Configuration knobs

The “which doctypes are searched and in what order” list is configured in:

- `Global Search Settings` (single DocType)
  - table field: `allowed_in_global_search` (child table: `Global Search DocType`)

Defaults can be provided by apps via hook:

- `global_search_doctypes` hook read in `frappe/desk/doctype/global_search_settings/global_search_settings.py`

---

## 2) Website Search (`frappe.search.web_search`) — Whoosh-based

### What it is

Website Search is a separate system used by the website’s header search box.

JS entrypoint:

- `frappe/website/js/website.js` calls `method: "frappe.search.web_search"`

Python entrypoint:

- `frappe/search/__init__.py:web_search(...)` → `WebsiteSearch(...).search(...)`

### Storage

Website search uses **Whoosh** indexes stored on the filesystem under the current site:

- `frappe.get_site_path("indexes", index_name)`

For the website index, the index name is `"web_routes"`.

### Index contents

Website search indexes **rendered web routes** (not raw DocType rows). Each indexed document stores:

- `title`: page `<title>` (or route)
- `path`: route (e.g. `"docs"`, `"about"`, `"/products/item-1"`)
- `content`: extracted page text from the `.page_content` element (best-effort)

### How indexing works

Core implementation:

- `FullTextSearch` wrapper: `frappe/search/full_text_search.py`
- Website specialization: `frappe/search/website_search.py`

Index build:

- `build_index_for_all_routes()` renders and indexes:
  - static pages across installed apps’ `www/` (`.md`, `.html`)
  - published documents that have web view enabled and opted in for indexing
- Each route is rendered as **Guest**, parsed via BeautifulSoup, and indexed.

Incremental updates:

- `update_index_for_path(path)` re-indexes one route.
- `remove_document_from_index(path)` deletes one route entry.

### How retrieval works

Search uses Whoosh’s `MultifieldParser` with:

- fields: `["title", "content"]`
- fuzzy term matching (`FuzzyTermExtended`)
- field boosts: `title` boosted higher than `content`
- `scope` filtering is implemented as a prefix filter on `path`

Results include highlight snippets:

- `title_highlights`, `content_highlights`

---

## 3) SQLite Search Framework (`frappe.search.sqlite_search`)

### What it is

`SQLiteSearch` (`frappe/search/sqlite_search.py`) is an **app-extensible** FTS framework built around SQLite FTS5.

Apps register search classes via a hook:

- `sqlite_search = ["my_app.search.MySearch"]`

### Storage

Each search class writes to a dedicated SQLite database file under the current site:

- default: `sites/<site>/<INDEX_NAME>`

Indexes are built using an atomic “build to temp db → rename” strategy.

### Index contents

The index schema is class-defined:

- `INDEX_SCHEMA`:
  - `text_fields` (default: `["title", "content"]`)
  - `metadata_fields` (must include `doctype`, `name`; optionally `modified`, etc.)
  - `tokenizer` configuration
- `INDEXABLE_DOCTYPES`:
  - doctypes to index
  - field mappings and optional filters

### How indexing works

Two modes:

- **Full rebuild**: `build_index()` fetches all configured doctypes, prepares documents, bulk indexes them, and rebuilds spelling vocab/trigram tables.
- **Incremental**:
  - `index_doc(doctype, docname)`
  - `remove_doc(doctype, docname)`

Automatic lifecycle integration is provided via module-level helpers:

- `build_index_in_background()`
- `update_doc_index(doc, method=None)`
- `delete_doc_index(doc, method=None)`

### How retrieval works

`search(query, title_only=False, filters=None)`:

- expands query via spelling correction
- executes an FTS5 `MATCH` query
- supports metadata filtering
- returns:
  - highlighted title
  - content snippet
  - BM25 score + custom scoring pipeline
  - consistent summary metadata (duration, applied filters, corrections, etc.)

Unlike Desk Global Search, `SQLiteSearch` requires subclasses to implement:

- `get_search_filters()`: permission-aware filtering that can be as strict as needed (including row-level controls).

---

## Practical takeaway (today)

- **Desk Global Search** is **DB-native** and optimized for “search across doctypes you can read”, but is **doctype-level permission gated** and has limited ranking controls.
- **Website Search (Whoosh)** is **route/content based** and provides highlight snippets, independent of `__global_search`.
- **SQLiteSearch** is a **pluggable framework** for app-specific search with richer ranking and filtering, but currently uses SQLite as its storage engine.


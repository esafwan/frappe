# Search in Frappe: current architecture + extensible backend plan

This document describes:

- **How search works today** in Frappe Framework (indexing + retrieval + permissions).
- A **master plan** for adding pluggable search backends (SQLite FTS first) as an **external app** (add-on), so that different products (web storefront, POS, APIs, etc.) can opt in and control ranking, filters, and indexing.

---

## Mental model (today)

Frappe currently has **multiple search systems**, each optimized for a different surface:

1. **Global Search (Desk + API)**: DB-backed full-text search over `__global_search` rows.  
   Entry point: `frappe.utils.global_search.search`.
2. **Website Route Search (Whoosh)**: file-backed search index for rendered web routes.  
   Entry point: `frappe.search.web_search` / `frappe.search.website_search.WebsiteSearch`.
3. **SQLite Search Framework (FTS5)**: an **app-defined** indexing + retrieval framework backed by a per-site SQLite database file.  
   Base class: `frappe.search.sqlite_search.SQLiteSearch`.

These systems are **not** the same thing. In particular:

- `frappe.utils.global_search` is **not Whoosh-based**; it uses DB full-text features (MariaDB / Postgres) over the `__global_search` table.
- `frappe.search.full_text_search.FullTextSearch` is a generic Whoosh wrapper and is used today by **website route search**, not by global search.

---

## 1) Global Search (`__global_search`)

### What it is

Global Search is the Desk-level “search across doctypes” experience implemented via:

- **Storage**: table `__global_search`
- **Indexing**: document lifecycle → enqueue update → periodic sync into DB table
- **Retrieval**: DB full-text query per “word”, then merged/sorted + permission filtered

Primary code: `frappe/utils/global_search.py`.

### Data model

`__global_search` stores one row per document:

- `doctype` (str)
- `name` (str)
- `content` (text): concatenation of selected field values as labeled strings
- `published` (int): website visibility bit
- `title` (str): website title (when relevant)
- `route` (str): website route (when relevant)

### How documents become searchable (field selection)

Searchable fields are determined by DocType metadata via `in_global_search`:

- DocFields marked `in_global_search = 1` are included.
- Child table fields can be included; child rows are pulled and appended to the parent’s `content`.

This is why changing “which fields are searchable” often requires a rebuild: you are changing what gets written into `__global_search.content`.

### Indexing lifecycle

**Step A — on every save, enqueue an update**

On document save, Frappe calls `update_global_search(self)` from the post-save path:

- `frappe/model/document.py` calls `update_global_search(self)` after `notify_update()` and before `save_version()`.
- `update_global_search()` computes the `content` string (including child table search fields) and pushes a JSON payload to the Redis list `global_search_queue`.
- If Redis is unavailable, it syncs directly (except during tests, where it should not fail silently).

**Step B — on delete, remove the row**

On deletion, `frappe.model.delete_doc.delete_doc()` calls `delete_for_document(doc)` which deletes the `__global_search` row for that document.

**Step C — periodic sync into `__global_search`**

Queued updates are applied by `sync_global_search()`:

- Runs in batches by draining `global_search_queue`.
- Dedupes by `(doctype, name)` before writing.
- Writes via DB-specific upsert semantics.

This sync is scheduled in core hooks:

- `frappe/hooks.py` schedules `frappe.utils.global_search.sync_global_search` every 15 minutes.

### Rebuilding for a DocType

`rebuild_for_doctype(doctype)` performs a full re-index of a single doctype into `__global_search`:

- Deletes existing rows for the doctype
- Pulls documents (excluding `docstatus=2`, and respecting `enabled/disabled` fields if present)
- Collects parent + child values and inserts in bulk

This is used when the DocType’s global-search field configuration changes.

### Retrieval lifecycle (Desk/API)

Entry point: `frappe.utils.global_search.search(text, start=0, limit=20, doctype="")`

High-level behavior:

- **Doctype allow-list**: intersection of:
  - doctypes allowed by Global Search Settings (`Global Search Settings.get_doctypes_for_global_search`)
  - doctypes the current user can read (`frappe.get_user().get_can_read()`)
- **Query parsing**: the input can contain `&` to represent multiple required “words”.
- **Execution**: for each unique word (split by `&`), run a DB full-text query against `__global_search.content` and collect matches.
- **Ranking**:
  - Uses a DB-specific `Match(...).Against(word)` expression via Query Builder.
  - Results are ordered by the DB’s rank output (descending).
- **Enrichment**: best-effort fetch of `image` / `title` fields if the target doctype defines them.

### Website-oriented retrieval (guest)

Entry point: `frappe.utils.global_search.web_search(text, scope=None, start=0, limit=20)`

Behavior:

- Only returns rows where `published = 1`.
- Optional `scope` limits by `route LIKE '{scope}%'`.
- Uses MariaDB boolean full-text or Postgres tsvector query (via `multisql`).
- Applies an additional lightweight relevance sort based on word overlap with `title`.

### Operational switches / constraints

- `disable_global_search` can disable indexing and syncing (see guard checks in `global_search.py`).
- This system’s capabilities and ranking are tied to the underlying DB engine and configuration.

---

## 2) Website Route Search (Whoosh)

### What it is

Website Route Search is a **Whoosh-backed** index used for searching website pages and routes.

Primary code:

- Whoosh wrapper: `frappe/search/full_text_search.py`
- Website implementation: `frappe/search/website_search.py`
- Whitelisted API: `frappe/search/__init__.py` (`frappe.search.web_search`)

### Storage & schema

- Index directory: `sites/<site>/indexes/<index_name>`  
  (`frappe.search.full_text_search.get_index_path`)
- Default website index name: `web_routes`
- Website schema (stored fields): `title`, `path`, `content`

### Indexing lifecycle

The base Whoosh wrapper (`FullTextSearch`) provides the following primitives:

- `build()`: fetch all documents → write a fresh index
- `update_index_by_name(doc_name)`: fetch one document → delete old → add new
- `remove_document_from_index(doc_name)`: delete a document by key field

`WebsiteSearch` implements:

- `get_items_to_index()`: collects:
  - static pages under each installed app’s `www/` (both `.md` and `.html`)
  - published “web-view” doctypes that opted in to `index_web_pages_for_search`
- `get_document_to_index(route)`: renders the route as Guest, extracts `.page_content` text, stores `title` + `content`

The “build all routes” path uses a file lock to avoid concurrent rebuilds:

- `frappe.search.website_search.build_index_for_all_routes()` uses `filelock("building_website_search")`

### Retrieval lifecycle

`WebsiteSearch.search(text, scope=None, limit=20)`:

- Uses Whoosh `MultifieldParser` over configured search fields (defaults: `title`, `content`).
- Applies **field boosts** (earlier fields get higher weight).
- Uses fuzzy term matching via `FuzzyTermExtended`.
- Supports **scoping** by prefix-filtering the document id (`path`) (useful to constrain to `/docs`, etc.).
- Returns highlight snippets for `title` and `content`.

Public API:

- `frappe.search.web_search(query, scope=None, limit=20)` is whitelisted for guest use.

---

## 3) SQLite Search Framework (FTS5)

### What it is

`frappe.search.sqlite_search.SQLiteSearch` is an **app-facing framework** for building a search index in a per-site SQLite database (FTS5), with:

- FTS5 query execution + snippets/highlights
- pluggable scoring pipeline (BM25 + recency + custom boosts)
- optional spelling correction (vocabulary + trigram index)
- per-user permission filtering (app supplies filters)

This framework is **separate** from global search: it does not populate `__global_search`.

Primary code: `frappe/search/sqlite_search.py`  
Framework documentation: `frappe/search/sqlite_search.md`

### Storage

- Index is a SQLite database file stored under the site path: `sites/<site>/<db_name>`
- Temporary build file is written as `*.temp.db` and swapped atomically.

### Index schema (FTS5 table)

The framework creates:

- `search_fts` virtual table (FTS5), with:
  - `doc_id UNINDEXED` (usually `{doctype}:{name}`)
  - configurable `text_fields` (default: `title`, `content`)
  - configurable `metadata_fields` stored as `UNINDEXED` columns (default includes `doctype`, `name`, and optionally `modified`)
  - configurable tokenizer (default: `unicode61 remove_diacritics 2`)
- `search_vocabulary` + `search_trigrams` for spelling correction

### Indexing lifecycle

Index build (`build_index()`):

- Creates a temp DB, ensures FTS tables exist
- Pulls documents for each configured doctype via Query Builder
- Normalizes documents into a consistent schema (`prepare_document`)
- Bulk writes into the FTS index in chunks
- Builds vocabulary and trigram index
- Atomically replaces the old DB file

Incremental updates:

- `index_doc(doctype, docname)`: upserts a single document
- `remove_doc(doctype, docname)`: deletes by `doc_id`

### Retrieval lifecycle

Search (`search(query, title_only=False, filters=None)`):

- Combines user-supplied filters with permission filters returned by `get_search_filters()`
- Expands query with spelling corrections (optional)
- Builds an FTS5 query string (quoted terms with prefix `*` for longer words)
- Executes SQL against `search_fts`:
  - uses `bm25(search_fts)` for base ranking
  - uses `highlight()` and `snippet()` for display fields
- Applies a scoring pipeline (multiplicative boosts) and returns both original and modified ranks

### How it plugs into apps (today)

Apps can register one or more `SQLiteSearch` subclasses via the `sqlite_search` hook.

Core Frappe hooks then provide:

- Doc event integration:
  - on update: `frappe.search.sqlite_search.update_doc_index`
  - on trash: `frappe.search.sqlite_search.delete_doc_index`
- Scheduled maintenance:
  - every 15 minutes: `frappe.search.sqlite_search.build_index_if_not_exists`

This pattern (hook registration + generic event dispatcher + scheduled health checks) is a strong reference point for designing pluggable search backends.

---

## Master plan: pluggable search backends as an external app

### Goals

Build an add-on app (example: `frappe_search`) that can provide:

- multiple **backends** (SQLite FTS first; later others)
- multiple **search profiles** (e-commerce catalog, POS item search, API search, etc.)
- consistent API surface (query, filters, paging, ranking controls)
- controllable **ranking** (field weights, recency, boosts, business rules)
- predictable **indexing** (what gets indexed, when, and how it’s updated)
- permission-aware retrieval with clear responsibility boundaries

Critically: this must work **without modifying Frappe core**.

### Key design principle: separate “search product surfaces”

Avoid one monolithic “global search replacement”. Instead define search surfaces:

- **Catalog Search** (web / guest)
- **POS Search** (fast prefix, SKU/barcode heavy)
- **API Search** (stable schema, explicit filters)
- **Desk Search** (maybe keep existing `__global_search` until replaced intentionally)

Each surface can map to one backend and one index profile.

### Proposed app-level architecture

#### 1) Backend interface (contract)

In the add-on app, define a small, stable interface (Python protocol / ABC), for example:

- `ensure_index(profile) -> None`
- `rebuild(profile) -> None`
- `index_doc(profile, doctype, name) -> None`
- `remove_doc(profile, doctype, name) -> None`
- `search(profile, query, *, filters, start, limit, options) -> SearchResult`

Where `SearchResult` is a consistent shape:

- `results[]`: `{doctype, name, title?, snippet?, score, rank, route?, image?, meta...}`
- `summary`: timing, matches, applied filters, corrected query, etc.

This keeps “callers” (APIs/UI) insulated from backend differences.

#### 2) Profiles (what is indexed + how)

Profiles define:

- **doctypes** to index and field mappings
- which fields are **searchable vs metadata**
- per-doctype filters (exclude disabled, docstatus, etc.)
- ranking configuration (weights, boosts, recency half-life)
- permission filter strategy (row-level filters, allow-lists, joins, etc.)

SQLite FTS profile can map 1:1 to the existing `SQLiteSearch` configuration style:

- `INDEX_SCHEMA`
- `INDEXABLE_DOCTYPES`
- `get_search_filters()`
- scoring functions / pipeline

#### 3) Index update plumbing (doc events + queue)

Recommended pattern (mirrors existing global search + SQLiteSearch patterns):

- **Doc events** enqueue lightweight “index tasks” (doctype, name, action)
- A background worker/scheduler drains the queue and calls the backend
- Bulk rebuilds are explicit admin operations (with progress + locks)

As an external app, you implement this via your app’s `hooks.py`:

- `doc_events`: register your event handlers (avoid per-doctype wiring by using `"*"` + dispatcher)
- `scheduler_events`: periodic sync / health check jobs

#### 4) API layer (explicit, versioned)

Expose app-owned endpoints instead of replacing core endpoints by default:

- `frappe_search.api.catalog_search`
- `frappe_search.api.pos_search`
- `frappe_search.api.search` (generic, profile-driven)

This allows gradual adoption and avoids surprising Desk behavior.

Optional advanced integration:

- Use `override_whitelisted_methods` in your app to override `frappe.utils.global_search.search` *only if* the site config enables it.

#### 5) Configuration & UX

Add-on app should ship a small, clear configuration surface:

- enabled backend per profile
- storage path strategy (e.g. `sites/<site>/search/<profile>.db`)
- rebuild/optimize commands + UI affordances (and safe locks)
- ranking presets with sensible defaults

#### 6) Observability & safety

Plan for:

- index versioning + migrations
- health checks (“index exists”, “last updated at”, “row counts”)
- performance budgets per surface (POS vs catalog vs API)
- safe fallbacks (if backend unavailable, return empty + telemetry, or fallback to DB search)

### Backend roadmap

**Phase 0 — document + align**

- Document current state (this file) and list the “search surfaces” we actually need.

**Phase 1 — SQLite FTS backend in add-on app**

- Implement profile-driven indexing similar to `SQLiteSearch` (FTS5 + ranking controls).
- Ship explicit APIs for web/pos, not replacing Desk search.
- Provide rebuild CLI + scheduler-based incremental updates.

**Phase 2 — unify + expand backends**

- Add a backend registry + routing rules (per profile, per site).
- Add future backends as needed (e.g. remote service, Postgres-native, Meilisearch, etc.).

### Practical note: reuse vs reimplement

Frappe already contains a mature `SQLiteSearch` implementation and docs (`frappe/search/sqlite_search.py`, `frappe/search/sqlite_search.md`). For an external app, you can:

- **Reuse** it as a dependency (thin wrapper + app-owned configuration + APIs), or
- **Fork**/reimplement it under your app namespace if you need stricter boundaries.

Either way, keep the **backend contract + profile routing** in your app so that adding a second backend later is just a registry addition, not a rewrite.


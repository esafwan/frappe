# Master plan: pluggable search backends via an external app

This plan proposes a **search backend framework** that can be shipped as a *separate Frappe app* (not inside the `frappe` app), enabling:

- an optional **MariaDB Full-Text Search backend** (first target),
- future backends (e.g. Postgres `tsvector`, Meilisearch, OpenSearch, Typesense, etc.),
- **surface-specific routing** (Desk omnibox vs website search vs product search APIs),
- **better ranking control**, and
- **clear extension points** for apps (index schema, scoring signals, filters).

The key constraint: **no core Frappe patching** required; integration should happen via hooks and public APIs.

---

## Goals

- Provide a **stable contract** for:
  - indexing (full + incremental),
  - querying (with ranking + snippets),
  - permission filtering,
  - admin-facing configuration.
- Allow a site/admin to **choose a backend per “search surface”**:
  - Desk global search (omnibox)
  - Website search (route search)
  - App-specific endpoints (e-commerce, POS, etc.)
- Make backends **optional** and **replaceable**:
  - “DB-native” mode (MariaDB FTS / Postgres TS / SQLite FTS) as first-class.
  - external engines as future implementations.
- Preserve a safe fallback:
  - if the backend is misconfigured or not indexed, fall back to existing behavior.

---

## Non-goals (for the first iteration)

- Replacing every search feature in Frappe. Start with a **parallel** backend and selective routing.
- Implementing a universal, perfect permission model across all doctypes. Instead: define a contract so each backend can be *as strict as the surface requires*.
- Solving multi-language stemming/tokenization for all languages on day one. Tokenization should be backend-configurable.

---

## Proposed architecture (external app)

### 1) Concepts

**Search Surface**

An explicit identifier for “where the search is used”, e.g.:

- `desk_global`
- `website_routes`
- `api:ecommerce_products`
- `api:pos_items`

**Search Backend**

A backend implementation that can:

- build/rebuild indexes,
- accept incremental updates,
- execute queries with ranking and snippet/highlight support.

**Search Index Definition**

Surface-specific “what to index” configuration:

- doctypes + fields (and optional joins/derived fields),
- filters (e.g., “only published products”),
- weighting/ranking signals (field boosts, recency, popularity, business rules),
- permission filtering strategy.

### 2) Hook-based registration

The external app should define a hook that apps can contribute to, for example:

- `search_backends = ["my_search_app.backends.mariadb.MariaDBFTSBackend", ...]`
- `search_indexes = ["my_search_app.indexes.WebsiteRoutesIndex", "my_search_app.indexes.DeskGlobalIndex", ...]`

This mirrors the existing pattern used by `sqlite_search` today, but generalized for multiple storage engines.

### 3) Core contract (interfaces)

Define minimal abstract interfaces inside the external app.

Suggested contracts (Python-side):

- `SearchBackend`:
  - `backend_id: str`
  - `supports(surface: str) -> bool`
  - `ensure_schema(index: SearchIndex) -> None`
  - `build(index: SearchIndex, *, force: bool = False) -> BuildReport`
  - `index_doc(index: SearchIndex, doctype: str, name: str) -> None`
  - `remove_doc(index: SearchIndex, doctype: str, name: str) -> None`
  - `query(index: SearchIndex, request: SearchRequest) -> SearchResponse`

- `SearchIndex` (surface definition):
  - `surface: str`
  - `index_id: str` (unique)
  - `get_documents() -> Iterable[IndexDocument]` (full rebuild)
  - `get_document(doctype, name) -> IndexDocument | None` (incremental)
  - `get_permission_filter(user) -> PermissionFilter` (surface-controlled)
  - optional: `get_ranking_config() -> RankingConfig`

Unified request/response types:

- `SearchRequest`: `query`, `limit`, `offset`, `filters`, `user`, `scope`
- `SearchResponse`:
  - `results: list[SearchResult]`
  - `summary: {duration_ms, total_matches, returned_matches, backend_id, index_id, warnings...}`

Result shape should include:

- stable identifiers: `doctype`, `name`, `route?`
- display fields: `title`, `snippet`, `image?`
- ranking: `score`, `rank`, and backend-specific signals (optional)

### 4) Backend selection + routing

The app should provide a registry and router:

- `get_backend_for_surface(surface) -> SearchBackend`
- `search(surface, ...) -> SearchResponse`

Selection order:

1. explicit per-surface config in a Settings doctype (see below),
2. per-app default mapping (via hooks),
3. fallback to built-in Frappe behavior.

### 5) Admin configuration model

Provide a single “Search Settings” doctype in the external app with:

- backend selection per surface
- backend parameters:
  - tokenizer, stopwords, min token length
  - field boosts
  - ranking switches (recency, exact-match boost, popularity signals)
- index definitions per surface:
  - doctypes/fields
  - filters
  - rebuild controls + status (last built, doc count, errors)

This is where “more control for e-commerce / APIs / POS” lives: **surface-specific config**, not one global config.

### 6) Index maintenance model

Support both:

- **Full rebuild**:
  - manual trigger (UI)
  - scheduled (nightly / weekly)
  - safe/atomic rebuild where possible
- **Incremental updates**:
  - “on save” indexing for targeted doctypes/fields
  - “on delete” removal

Implementation detail:

- Use document event hooks from apps:
  - `doc_events = {"*": {"on_update": ..., "on_trash": ...}}`
  - or better: register only for doctypes used by indexes (avoid global hooks).

For reliability:

- enqueue indexing operations (Redis queue) and drain in batches (like current `global_search_queue` approach).

---

## MariaDB FTS backend (first backend)

### Why this backend first

MariaDB is common in Frappe deployments, and DB-native FTS avoids external infra.

### Key design decision: where the FTS index lives

Two viable models:

1. **Generic index table(s)** managed by the external app:
   - e.g. `__search_index_<index_id>` with columns:
     - `doctype`, `name`, `title`, `content`, `route`, `published`, plus metadata fields
     - `FULLTEXT(title, content)` (or just content)
   - Pros: backend is decoupled from DocType schema; can index arbitrary subsets; avoids altering app tables.
   - Cons: duplication of content; needs write pipeline; needs cleanup.

2. **Index in-place on existing DocType tables**:
   - Pros: less duplication.
   - Cons: hard to generalize; expensive migrations; app tables vary; not feasible as an optional external app without deep coupling.

For a “pluggable framework app”, **model (1)** is strongly preferred.

### Tokenization + query mode

Expose configurable defaults:

- NATURAL LANGUAGE vs BOOLEAN mode
- prefix matching strategy (`+term*` boolean mode)
- stopwords and min token length (documented as server-level requirements)

### Ranking + control points

MariaDB provides relevance score via `MATCH(...) AGAINST(...)`.

The backend can expose:

- field boosts:
  - `MATCH(title) AGAINST(...) * w_title + MATCH(content) AGAINST(...) * w_content`
- recency:
  - combine with `modified` metadata to adjust score (post-processing)
- business boosts:
  - popularity / sales / click-through metrics from metadata fields

Implementation strategy:

- Use DB relevance as the first-stage score.
- Apply a second-stage scoring pipeline in Python (optional) for deterministic business boosts.

---

## Integration strategy with Frappe (without core patches)

### Desk omnibox (Global Search)

Today, Desk calls `frappe.utils.global_search.search` directly from JS.

To avoid patching Frappe:

- Provide **new API endpoints** (e.g. `my_search_app.api.search`) and allow apps/UIs to call it.
- Optionally provide a small “UI override” bundle (JS hook) that swaps the method used by Desk’s search UI for sites that opt in.

If later core changes are acceptable, the best long-term integration is to introduce a Frappe-level hook like:

- `global_search_provider = "path.to.provider"`

But the plan here assumes **external app only**, so it should start with additive endpoints and opt-in UI wiring.

### Website search

Website search currently calls `frappe.search.web_search` (Whoosh).

An external app can:

- add a new endpoint (e.g. `my_search_app.website.search`) and provide a website JS override.
- or provide a drop-in implementation that keeps the same response contract used by `website.js` (title, path, highlights).

### App-specific endpoints (e-commerce, POS, APIs)

This is the easiest surface to adopt:

- apps call the external app’s API directly,
- define surface-specific index definitions and ranking controls,
- bypass the limitations of Desk Global Search.

---

## Phased delivery plan

### Phase 0 — Documentation + baseline contracts

- Document current search systems (this repo).
- In the external app: implement the interfaces and registry/router.
- Add a minimal Settings doctype + per-surface backend mapping.

### Phase 1 — MariaDB FTS backend MVP (index-table model)

- Implement one `SearchIndex` for a concrete surface (e.g. `api:ecommerce_products`).
- Implement:
  - full rebuild job
  - incremental index queue + batch drain
  - query API with ranking + snippets
- Provide a reference UI/API client usage.

### Phase 2 — Parity surface: Desk-like global search (optional)

- Implement a “desk_global” index definition:
  - controlled doctype list
  - content extraction similar to current global search
  - doctype-level permission gating for parity
- Provide opt-in JS override to route Desk calls to the new endpoint.

### Phase 3 — Ranking controls + observability

- add scoring pipeline hooks:
  - recency, exact-match boost, field boosts, popularity
- add metrics:
  - query latency, matches count, rebuild duration, queue depth
- add admin UX:
  - “Rebuild index”, “Index status”, warnings/errors

### Phase 4 — Additional backends

- Postgres TS backend (if needed) using `tsvector` + `ts_rank`.
- External engines (Meilisearch/OpenSearch) as optional modules.

---

## Compatibility + migration notes

- This plan is intentionally **parallel**: existing Frappe search remains the default.
- Adoption is **surface-by-surface**:
  - start with high-value public/API search (e-commerce), then expand.
- Ensure graceful fallback:
  - if index is missing or backend errors, return a structured error and/or fall back to existing behavior depending on surface requirements.


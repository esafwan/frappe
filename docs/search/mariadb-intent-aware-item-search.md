# MariaDB search in Frappe: how it works + no-code levers

This note documents how Frappe’s current **MariaDB-backed search** behaves (why “milk” matches “chocolate milk”), what you can influence **without code**, and a simple next step to reduce “intent ambiguity” for product / item catalogs.

---

## What search paths are we talking about?

In Frappe there are two relevant (often conflated) search paths:

1. **Desk Global Search (Awesome Bar / omnibox)**
   - Backend: `frappe.utils.global_search.search`
   - Storage: MariaDB table `__global_search` with `FULLTEXT(content)` index
   - Query primitive: `MATCH(content) AGAINST(...)` ranking

2. **Link field / “Item picker” search (and many app-level lookups)**
   - Backend: `frappe.desk.search.search_link` → `search_widget`
   - Storage: the DocType’s own table (e.g. `tabItem`)
   - Query primitive: SQL `LIKE "%<txt>%"` across `name`, `title_field`, and `search_fields`, plus a prefix-boost sorter

Both can surface “milk-ish” results, but they’re **different engines** and have **different knobs**.

---

## A. Desk Global Search: MariaDB data model & ranking

### Where the data comes from

- Frappe computes “global-search content” by reading DocFields marked as **global-search fields** on a DocType (and optionally its child tables).
- These values are concatenated into a single `content` string and stored in `__global_search`.

Implementation: `frappe/utils/global_search.py`

### How MariaDB stores it

Frappe creates `__global_search` on MariaDB with a `FULLTEXT(content)` index and `ENGINE=MyISAM`.

Implementation: `frappe/database/mariadb/database.py` (`create_global_search_table`)

### How retrieval/ranking works

Desk Global Search uses MariaDB full-text ranking on the **flattened `content` blob**:

- For each token (split by `&`), it computes a rank using `MATCH(content) AGAINST(token)` and orders by rank descending.
- After that, it re-orders by the **DocType priority list** from “Global Search Settings” (doctype-level ordering).

Implementation: `frappe/utils/global_search.py` (`search`)

### Why “milk” returns “chocolate milk”

Because `content` is a **bag of text**. If “Chocolate milk”, “Milk powder”, and “Milk” all contain the token “milk”, full-text retrieval will treat them as related unless you add **structure** (intent signals) or reduce what’s indexed.

In other words:

- **Search engines retrieve** matching text.
- **Without intent fields**, ranking can’t reliably separate “base product” vs “derived/processed product”.

---

## B. Link field / Item search: where it ranks differently

Link field search is **not** `__global_search`. It:

- searches with `LIKE "%txt%"` over:
  - `name`
  - the DocType’s `title_field` (if set)
  - the DocType’s `search_fields` list (if set)
- then boosts results where the value **starts with** the query (prefix matches come first)

Implementation: `frappe/desk/search.py` (`search_widget`, `relevance_sorter`)

Practical implication:

- If your “base intent” item is literally named `Milk`, and your variants are named `Chocolate Milk`, `Strawberry Milkshake`, etc., then searching `milk` will usually put the base/clean item near the top because **prefix and exact matches win**.
- If variants start with modifiers (e.g. `Chocolate Milk`), they will rank closer to `Milk` than you’d like unless you standardize names or reduce searchable fields.

---

## What can you influence (no code)

### 1) DocType-level knobs (metadata / configuration)

These are the highest-signal, Frappe-native “no code” levers:

- **Global Search Settings (doctype ordering)**:
  - You can control which doctypes appear in Desk Global Search, and in what order.
  - DocType: `Global Search Settings` with child table `Global Search DocType`
  - Implementation: `frappe/desk/doctype/global_search_settings/global_search_settings.py`

- **Which fields are indexed into `__global_search`**:
  - This is controlled by “global search” field flags on DocFields.
  - Fewer, more “canonical” fields = less noise (less accidental overlap like “tomato ketchup” matching “tomato” too strongly).
  - Implementation reads `meta.get_global_search_fields()` in `frappe/utils/global_search.py`.

- **Which fields are searched for Link/Item pickers**:
  - Controlled by the DocType’s `title_field` and `search_fields`.
  - Link search will always include `name`; adding verbose descriptive fields often increases ambiguity.
  - Implementation: `frappe/desk/search.py`.

### 2) Data-level knobs (naming & structured text)

These work immediately and don’t require any framework changes:

- **Naming convention for ambiguous products**
  - Put the **canonical entity as the prefix** for the base product and most close variants.
  - Keep modifiers after the canonical token, consistently.

Example (milk):

- `Milk` (base)
- `Milk - Chocolate` (variant)
- `Milk - Strawberry` (variant)
- `Milk - Powder` (derived)

Example (tomato):

- `Tomato` (base)
- `Tomato - Cherry` (variant)
- `Tomato - Paste` (derived)
- `Tomato - Ketchup` (processed / condiment)

This directly improves Link search (prefix boost) and usually improves full-text ranking (shorter/cleaner docs).

- **A single “Search Keywords”/“Canonical” field (optional, still no code)**
  - If your Item/Product DocType already has a lightweight field you can curate (or you can add one via Customize Form), keep it small:
    - canonical entity first (`milk`)
    - then a small set of controlled modifiers (`chocolate`, `powder`)
  - Then ensure only that field (and `item_name`/`name`) participates in search, while long descriptions do not.

### 3) Database-level knobs (MariaDB configuration)

These are real, but they mostly affect *recall/precision* and performance, not “intent”:

- MariaDB FULLTEXT stopword lists, minimum word length, boolean mode syntax, etc.
- They can reduce noisy matches (e.g. tiny tokens), but they won’t reliably separate “tomato” base vs “tomato ketchup”.

---

## Simple next step (no major development): “reduce noise + enforce prefix intent”

Goal: make the default (“milk” means plain milk) emerge naturally from existing ranking behavior.

### Step 1 — Pick 10–20 ambiguous canonical entities

Start with the high-impact set you listed (milk, tomato, oil, rice, phone…).

### Step 2 — Standardize item names for those entities

For each entity:

- Ensure the base product name is exactly the canonical token (or the canonical token as the clear prefix).
- Move modifiers after the canonical token consistently (e.g. `Milk - Chocolate`, not `Chocolate Milk`).

This is the fastest win because it improves:

- Link field search (prefix/exact match rises)
- Many human UIs that sort lexicographically

### Step 3 — Remove verbose fields from search inputs (configuration)

For your Item/Product DocType:

- Keep search focused on `name` + a small curated set (e.g. `item_name`, `item_code`, a short keywords field).
- Avoid including long descriptions, marketing copy, recipes, etc., in:
  - global search indexed fields (for Desk Global Search)
  - `search_fields` (for Link/Item picker search)

This reduces “token overlap” that causes derived/processed products to compete with base items.

### Step 4 — Rebuild / refresh indexes

After metadata changes, rebuild the relevant indexes so results reflect the new field set:

- Desk Global Search: rebuild the affected doctype’s `__global_search` entries (implementation supports per-doctype rebuild in `frappe/utils/global_search.py`).

---

## Where to add “intent-aware ranking” later (for planning)

If/when you decide to implement the “Product Search Profile” approach, the clean integration point is **not** the MariaDB FULLTEXT primitive itself, but **a scoring/ranking layer on top of retrieval**, with optional curated fields.

Today’s no-code approach is the minimal path:

- **Make the base intent item win by name and field selection**
- Add curated intent only for the ambiguous ~20% later


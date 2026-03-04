# Frappe Framework Design System Architecture

This document provides a complete technical understanding of the Frappe UI design system for engineers planning to override or replace it.

---

## 1. Design System Overview

### Styling Technologies

| Technology | Usage |
| ---------- | ----- |
| **SCSS/SASS** | Primary styling language for Desk, Website, and shared components |
| **CSS** | Compiled output; some legacy/vendor CSS (Bootstrap, fonts, leaflet, etc.) |
| **LESS** | Octicons only: `frappe/public/css/octicons/octicons.less`. Note: The build consumes the pre-compiled `octicons.css`, not the `.less` file. |
| **PostCSS** | Autoprefixer, RTL (rtlcss). (esbuild's `minify: PRODUCTION` handles minification, not cssnano as a PostCSS plugin) |
| **Bootstrap 4.6.2** | Base component framework; variables overridden in SCSS |
| **CSS Custom Properties** | Design tokens (Espresso) and theme variables |

### UI Layer Structure

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Frappe Backend (Python)                             │
│  • bootinfo (desk_theme, assets)  • hooks (app_include_css/js/icons)         │
│  • Jinja templates (desk.html)   • bundled_asset() → assets.json            │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Asset Build Pipeline                                 │
│  bench build → yarn build → esbuild.js → PostCSS + SASS → dist/css/*.css     │
│  Output: sites/assets/{app}/dist/css/*.css  +  assets.json                   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Desk UI (Single-Page App)                            │
│  • Vue 3 + jQuery  • desk.bundle.js/css  • data-theme, data-theme-mode       │
│  • Bootstrap + custom SCSS  • Espresso tokens  • dark.scss overrides        │
└─────────────────────────────────────────────────────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────────────┐
│                         Web UI (Server-Rendered)                             │
│  • website.bundle.css  • Website Theme (Jinja SCSS)  • Bootstrap overrides  │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
┌─────────────────────────────────────┼───────────────────────────────────────┐
│                         Component System                                     │
│  • Vanilla JS (frappe-control, form controls)  • Vue 3 components             │
│  • BEM-like class names  • CSS variables for theming                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Relationship Summary

| Layer | Role |
| ----- | ---- |
| **Frappe Backend** | Serves bootinfo, resolves assets via `assets.json`, injects CSS/JS via Jinja |
| **Desk UI** | Main app shell; loads `desk.bundle.css` + `desk.bundle.js`; theme via `data-theme` |
| **Web UI** | Public website; loads `website.bundle.css`; themed via Website Theme doctype |
| **Component system** | Form controls, modals, buttons, etc.; use shared SCSS + CSS variables |
| **CSS framework** | Bootstrap 4.6.2 with custom overrides; Espresso tokens for design tokens |

---

## 2. Asset Build Pipeline

### Build Chain

```
bench build [--production] [--apps frappe,erpnext] [--files frappe/desk.bundle.js]
    │
    └─► frappe.build.bundle()  [frappe/build.py]
            │
            └─► yarn run build  (or yarn run production)
                    │
                    └─► node esbuild  [esbuild/esbuild.js]
                            │
                            ├─► build_files()  → JS (esbuild + Vue)
                            ├─► build_style_files()  → CSS (esbuild + PostCSS)
                            └─► build_style_files(rtl_style=true)  → CSS (RTL)
```

### Build Tools

| Component | Tool | Config File | Path |
| --------- | ---- | ----------- | ---- |
| JS bundler | esbuild | `esbuild/esbuild.js` | Root |
| Vue plugin | esbuild-plugin-vue3 | `package.json` | Root |
| CSS pipeline | @frappe/esbuild-plugin-postcss2 | `esbuild/esbuild.js` | Root |
| SASS | sass | `esbuild/sass_options.js` | Root |
| PostCSS | autoprefixer, rtlcss | PostCSS plugin | Root |
| Minification | esbuild built-in | `esbuild/esbuild.js` | Root |
| Bench build | Python | `frappe/build.py` | Root |

### Build Configuration

| Entry | Value |
| ----- | ----- |
| **Input pattern** | `*.bundle.{js,ts,css,sass,scss,less,styl,jsx}` under `apps/*/public/**` |
| **Output dir** | `sites/assets/{app}/dist/` (js/, css/, css-rtl/) |
| **Output naming** | `[name].[hash].{js,css}` |
| **Asset manifest** | `sites/assets/assets.json`, `sites/assets/assets-rtl.json` |

### How `bench build` Works

1. `frappe.build.bundle()` in `frappe/build.py` calls `yarn run build` (or `production`) from the Frappe app root.
2. `package.json` scripts: `build` → `node esbuild`, `production` → `node esbuild --production`.
3. `esbuild.js`:
   - Discovers `*.bundle.*` files via `fast-glob`.
   - JS: `build_files()` → esbuild + Vue plugin + HTML plugin.
   - CSS: `build_style_files()` → PostCSS plugin with SASS + Autoprefixer + (optional) rtlcss.
   - Minification: esbuild's built-in `minify: PRODUCTION` config is used.
   - RTL: Same pipeline with `rtl_style: true` → output to `css-rtl/`.
4. Writes `assets.json` mapping bundle names (e.g. `desk.bundle.css`) to hashed paths (e.g. `/assets/frappe/dist/css/desk.bundle.ABC123.css`).
5. `make_asset_dirs()` symlinks `{app}/public` → `sites/assets/{app}` for static assets.

### SASS Options

- **File:** `esbuild/sass_options.js`
- **Include paths:** `node_modules` + app paths for `~` imports.
- **Importer:** `~bootstrap` resolves to `node_modules/bootstrap`.

---

## 3. Style Source Structure

### Directory Map

| Type | File / Directory | Relative Path | Purpose |
| ---- | ---------------- | ------------- | ------- |
| **SCSS bundle** | desk.bundle.scss | `frappe/public/scss/desk.bundle.scss` | Main Desk entry |
| **SCSS bundle** | website.bundle.scss | `frappe/public/scss/website.bundle.scss` | Website entry |
| **SCSS bundle** | report.bundle.scss | `frappe/public/scss/report.bundle.scss` | Report view |
| **SCSS bundle** | login.bundle.scss | `frappe/public/scss/login.bundle.scss` | Login page |
| **SCSS bundle** | email.bundle.scss | `frappe/public/scss/email.bundle.scss` | Email templates |
| **SCSS bundle** | print.bundle.scss | `frappe/public/scss/print.bundle.scss` | Print view |
| **SCSS bundle** | print_format.bundle.scss | `frappe/public/scss/print_format.bundle.scss` | Print format |
| **SCSS bundle** | web_form.bundle.scss | `frappe/public/scss/web_form.bundle.scss` | Web forms |
| **Desk SCSS** | index.scss | `frappe/public/scss/desk/index.scss` | Desk imports |
| **Desk SCSS** | variables.scss | `frappe/public/scss/desk/variables.scss` | Bootstrap + Espresso vars |
| **Desk SCSS** | css_variables.scss | `frappe/public/scss/desk/css_variables.scss` | Desk CSS vars |
| **Desk SCSS** | dark.scss | `frappe/public/scss/desk/dark.scss` | Dark mode overrides |
| **Desk SCSS** | typography.scss | `frappe/public/scss/desk/typography.scss` | Font sizes |
| **Common SCSS** | css_variables.scss | `frappe/public/scss/common/css_variables.scss` | Core CSS vars |
| **Common SCSS** | mixins.scss | `frappe/public/scss/common/mixins.scss` | Shared mixins |
| **Common SCSS** | global.scss | `frappe/public/scss/common/global.scss` | Global styles |
| **Common SCSS** | buttons.scss | `frappe/public/scss/common/buttons.scss` | Button styles |
| **Common SCSS** | controls.scss | `frappe/public/scss/common/controls.scss` | Form controls |
| **Common SCSS** | modal.scss | `frappe/public/scss/common/modal.scss` | Modal styles |
| **Common SCSS** | form.scss | `frappe/public/scss/common/form.scss` | Form base |
| **Common SCSS** | alert.scss | `frappe/public/scss/common/alert.scss` | Alerts |
| **Espresso** | _colors.scss | `frappe/public/scss/espresso/_colors.scss` | Color tokens |
| **Espresso** | _typography.scss | `frappe/public/scss/espresso/_typography.scss` | Typography tokens |
| **Espresso** | _shadows.scss | `frappe/public/scss/espresso/_shadows.scss` | Shadow tokens |
| **Espresso** | _borders.scss | `frappe/public/scss/espresso/_borders.scss` | Border radius |
| **Espresso** | _spacing.scss | `frappe/public/scss/espresso/_spacing.scss` | Spacing tokens |
| **Website SCSS** | index.scss | `frappe/public/scss/website/index.scss` | Website imports |
| **Website SCSS** | variables.scss | `frappe/public/scss/website/variables.scss` | Website vars |
| **Website SCSS** | css_variables.scss | `frappe/public/scss/website/css_variables.scss` | Website CSS vars |
| **Theme template** | website_theme_template.scss | `frappe/website/doctype/website_theme/website_theme_template.scss` | Jinja SCSS |
| **CSS** | bootstrap.css | `frappe/public/css/bootstrap.css` | Bootstrap (pre-built) |
| **CSS** | tree.css | `frappe/public/css/tree.css` | Tree view |
| **CSS** | octicons.css | `frappe/public/css/octicons/octicons.css` | Pre-compiled Octicons CSS |

### Import Hierarchy (Desk)

```
desk.bundle.scss
├── fonts (fontawesome, octicons.css, inter)
├── frappe-charts, plyr, leaflet CSS
├── desk/index.scss
│   ├── desk/variables.scss        ← imports espresso tokens
│   │   ├── espresso/_colors, _spacing, _typography, _shadows, _borders
│   │   ├── desk/typography.scss
│   │   ├── ~bootstrap/scss/functions
│   │   ├── ~bootstrap/scss/variables
│   │   ├── ~bootstrap/scss/mixins
│   │   ├── desk/css_variables.scss   ← imported by variables, not index
│   │   │   └── common/css_variables.scss
│   │   └── desk/dark.scss            ← dark mode overrides
│   ├── common/mixins, global, icons, alert
│   ├── ~bootstrap/scss/bootstrap     ← FULL bootstrap
│   ├── desk/global
│   ├── common/buttons, flex
│   ├── desk/mobile, module, form, navbar, modal, etc.
│   ├── common/controls, quill
│   └── desk/menu, sidebar_header, sidebar_card
└── highlight.js CSS
```

---

## 4. Design Tokens / Variables

### Espresso Tokens (`frappe/public/scss/espresso/`)

| Variable | File | Default Value | Used In |
| -------- | ---- | ------------- | ------- |
| `--gray-50` … `--gray-900` | _colors.scss | #f8f8f8 … #171717 | Everywhere |
| `--blue-50` … `--blue-900` | _colors.scss | Palette | Links, info, charts |
| `--red-*`, `--green-*`, etc. | _colors.scss | Palettes | Alerts, indicators |
| `--white-overlay-*`, `--black-overlay-*` | _colors.scss | Overlay scales | Overlays |
| `--linear-*`, `--angular-*` | _colors.scss | Gradient rules | Backgrounds |
| `--outline-gray-*` | _colors.scss | Semantic borders | Inputs, modals |
| `--surface-gray-*` | _colors.scss | Backgrounds | Cards, modals |
| `--ink-gray-*` | _colors.scss | Text | Typography |
| `--text-tiny` … `--text-12xl` | _typography.scss | 11px … 64px | Typography |
| `--weight-regular` … `--weight-black` | _typography.scss | 420 … 800 | Font weights |
| `--shadow-xs` … `--shadow-2xl` | _shadows.scss | Box shadows | Cards, modals |
| `--focus-default`, `--focus-blue`, `--focus-yellow` | _shadows.scss | Focus rings | Inputs, buttons |
| `--border-radius-tiny` … `--border-radius-full` | _borders.scss | 4px … 999px | Components |
| `--input-padding` | _spacing.scss | 6px 8px | Inputs |
| `--dropdown-padding` | _spacing.scss | 4px 8px | Dropdowns |
| `--grid-padding` | _spacing.scss | 10px 8px | Grid layout |

### Common CSS Variables (`frappe/public/scss/common/css_variables.scss`)

This file contains 65+ variables. Key examples:

| Variable | Default (Light) | Purpose |
| -------- | -------------- | ------- |
| `--padding-xs` … `--padding-2xl` | 5px … 40px | Spacing (`--padding-sm` is 7px) |
| `--margin-xs` … `--margin-2xl` | 5px … 40px | Spacing (`--margin-sm` is 10px) |
| `--page-max-width` | 900px | Form layout |
| `--navbar-height` | 48px | Navbar |
| `--bg-color`, `--fg-color` | white | Layout |
| `--control-bg` | var(--gray-100) | Inputs, buttons |
| `--btn-primary` | var(--gray-900) | Primary button |
| `--border-color` | var(--gray-200) | Borders |
| `--input-height` | 28px | Inputs |
| `--checkbox-size` | 14px | Checkboxes |
| `--diff-added`, `--diff-removed`, `--diff-changed` | Blue/Red/Green 200 | Diff visualizers |
| `--alert-text-*`, `--alert-bg-*` | Various | Form alerts |
| `--right-arrow-svg`, `--left-arrow-svg` | SVG values | Arrows icons |

### Desk CSS Variables (`frappe/public/scss/desk/css_variables.scss`)

| Variable | Purpose |
| -------- | ------- |
| `--xxl-width` … `--xs-width` | Breakpoints |
| `--page-head-height` | Page header |
| `--list-row-height` | List view |
| `--timeline-*` | Timeline layout |
| `--error-bg`, `--error-border` | Form constraint styling |

---

## 5. Typography System

### Font Stack

- **Variable:** `--font-stack`
- **Value:** `"InterVariable", "Inter", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", …`
- **Source:** `frappe/public/scss/espresso/_typography.scss`

### Heading Hierarchy

| Element | Source File | Style Definition |
| ------- | ----------- | ---------------- |
| `$h1-font-size` | desk/typography.scss | 1.75rem |
| `$h2-font-size` | desk/typography.scss | 1.5rem |
| `$h3-font-size` | desk/typography.scss | 1.25rem |
| `$h4-font-size` | desk/typography.scss | 1.125rem |
| `$h5-font-size` | desk/typography.scss | 0.875rem |
| `$h6-font-size` | desk/typography.scss | 0.6875rem |
| `--heading-color` | espresso/_typography.scss | var(--gray-900) |
| `--text-color` | espresso/_typography.scss | var(--gray-800) |
| `--text-muted` | espresso/_typography.scss | var(--gray-700) |

### Font Weights

| Variable | Value |
| -------- | ----- |
| `--weight-regular` | 420 |
| `--weight-medium` | 500 |
| `--weight-semibold` | 600 |
| `--weight-bold` | 700 |
| `--weight-black` | 800 |

### Typography Mixin

- **Mixin:** `@mixin get_textstyle($name, $weight)` in `espresso/_typography.scss`
- **Usage:** `@include get_textstyle("base", "regular")` → font-size, font-weight, letter-spacing

---

## 6. Component Styling System

### Styling Approach

- **Bootstrap 4.6.2** base with variable overrides.
- **CSS variables** for theming (light/dark).
- **BEM-like** class names (e.g. `.frappe-control`, `.form-control`, `.modal-header`).
- **Utility classes** from Bootstrap (`.d-flex`, `.p-2`, etc.).
- **Component-scoped** styles in SCSS modules.

### Component Style Map

| Component | Style File | Class Prefix | Variables Used |
| --------- | ---------- | ------------ | -------------- |
| Buttons | common/buttons.scss | `.btn`, `.btn-primary`, `.btn-default` | `--btn-primary`, `--control-bg`, `--border-radius` |
| Forms | common/form.scss, desk/form.scss | `.form-control`, `.frappe-control` | `--input-height`, `--control-bg`, `--border-radius-sm` |
| Modals | common/modal.scss | `.modal`, `.modal-content` | `--modal-bg`, `--border-color`, `--padding-*` |
| Alerts | common/alert.scss | `.alert`, `.alert-danger` | `--alert-text-*`, `--alert-bg-*` |
| Dropdowns | Bootstrap + variables | `.dropdown-menu` | `--shadow-2xl`, `--dropdown-*` |
| Navbar | desk/navbar.scss | `.navbar` | `--navbar-height`, `--navbar-bg` |
| Sidebar | desk/sidebar.scss | `.sidebar` | `--fg-color`, `--control-bg` |
| Cards | common/mixins (card) | `.frappe-card` | `--card-bg`, `--card-shadow` |
| Lists | desk/list.scss | `.list-row` | `--list-row-height`, `--border-color` |
| Tables | common/grid.scss | `.grid-head`, `.grid-body` | `--table-border-color` |
| Tags | desk/tags.scss | `.tag-pill` | `--bg-*`, `--text-on-*` |
| Toast | desk/toast.scss | `.toast` | `--toast-bg` |

---

## 7. Form System

### Form Layout

- **Container:** `.form-layout`, `.form-page`
- **Sections:** `.form-section`, `.section-head`, `.section-body`
- **Fields:** `.frappe-control` wrapping `.form-control` or custom controls

### Field Styling

| Element | Source | Style |
| ------- | ------ | ----- |
| `.form-control` | common/form.scss | `height: var(--input-height)`, `border-radius: var(--border-radius-sm)`, `padding: var(--input-padding)` |
| `.like-disabled-input` | common/form.scss | `background-color: var(--disabled-control-bg)`, `color: var(--disabled-text-color)` |
| `.head-title` | common/form.scss | `font-size: var(--text-xl)`, `font-weight: 700` |

### Validation States

- Bootstrap validation classes (`.is-invalid`, `.is-valid`) with CSS variable overrides.
- Error: `--error-bg`, `--error-border` (desk/css_variables.scss). Dark mode handles color inversion for `--error-bg`/`--error-border` appropriately.

### Label & Help Text

- Labels via Bootstrap `.form-label`.
- Help text: `.help-box` in `frappe-control` (dark.scss overrides for dark mode).

---

## 8. Shadow / Elevation System

| Shadow Level | CSS Variable | Value | Used In |
| ------------ | ------------ | ----- | ------- |
| xs | `--shadow-xs` | Multi-layer rgba shadows | Buttons |
| sm | `--shadow-sm` | 0px 1px 2px rgba(0,0,0,0.1) | Cards |
| base | `--shadow-base` | 0px 0px 1px + 0px 1px 2px | General |
| md | `--shadow-md` | 0px 0px 1px + 0.5px 2px + 2px 3px | Modals |
| lg | `--shadow-lg` | 0px 0px 1px + 0px 6px 8px | Popovers |
| xl | `--shadow-xl` | Multi-layer | Dropdowns |
| 2xl | `--shadow-2xl` | 0px 0px 1px rgba(0,0,0,0.2) + 0px 1px 3px rgba(0,0,0,0.05) + 0px 10px 24px -3px rgba(0,0,0,0.1) | Popovers, dropdowns |

### Focus Rings

| Ring | Variable | Use |
| ---- | -------- | --- |
| Default | `--focus-default` | General focus |
| Blue | `--focus-blue` | Primary focus |
| Green | `--focus-green` | Success |
| Yellow | `--focus-yellow` | Highlighted elements |
| Red | `--focus-red` | Error |

---

## 9. Layout System

### Containers

- **Bootstrap grid:** `$container-max-widths` in desk/variables.scss (sm: 540px, md: 840px, lg: 1090px, xl: 1290px).
- **Page max width:** `--page-max-width: 900px` for form content.

### Breakpoints

| Breakpoint | Value | Variable |
| ---------- | ----- | -------- |
| xs | 0 | `--xs-width` |
| sm | 576px | `$grid-breakpoints` |
| md | 768px | |
| lg | 992px | |
| xl | 1200px | |
| 2xl | 1440px | |

### Flexbox Utilities

- **Mixin:** `@mixin flex($dis: flex, $x: center, $y: center, $dir: row)` in common/mixins.scss.
- **Bootstrap:** `.d-flex`, `.justify-content-*`, `.align-items-*`.

### Spacing Utilities

- **Variables:** `--padding-xs` … `--padding-2xl`, `--margin-xs` … `--margin-2xl`. (e.g. `--padding-sm: 7px`, `--margin-sm: 10px`)
- **Bootstrap Spacers:** `$spacers` map (0 through 64) in `website/variables.scss` provides extensive Bootstrap spacing overrides.

---

## 10. Dark Mode Implementation

### Mechanism

| Mechanism | File | Description |
| --------- | ---- | ----------- |
| HTML attributes | desk.html | `data-theme-mode`, `data-theme` on `<html>` |
| Light/dark vars | common/css_variables.scss | `:root`, `[data-theme="light"]` |
| Dark overrides | desk/dark.scss | `[data-theme="dark"]` block |
| Semantic colors | espresso/_colors.scss | `[data-theme="dark"]` overrides for `--surface-*`, `--ink-*` |
| Theme switcher | theme_switcher.js | `frappe.ui.set_theme()`, `frappe.ui.get_current_theme()` |
| System preference | theme_switcher.js | `matchMedia("prefers-color-scheme: dark")` |
| MutationObserver | desk.js | Watches `data-theme-mode` changes |
| Server-side | sessions.py, user.py | `desk_theme` in bootinfo; `switch_theme()` persists to User |

### Theme Modes

| Mode | data-theme-mode | data-theme (effective) |
| ---- | ---------------- | ----------------------- |
| Light | `light` | `light` |
| Dark | `dark` | `dark` |
| Automatic | `automatic` | `light` or `dark` from `prefers-color-scheme` |

### Runtime Logic

1. `desk.html` sets `data-theme-mode` and `data-theme` from `desk_theme` (User preference).
2. `frappe.ui.set_theme()` updates `data-theme` on `document.documentElement`.
3. For `automatic`, `frappe.ui.dark_theme_media_query` drives updates.
4. `MutationObserver` in desk.js watches DOM and re-runs `set_theme()` when `data-theme-mode` changes.

---

## 11. Theme System

### Desk Theme (User)

| Aspect | Implementation |
| ------ | -------------- |
| **Storage** | User.desk_theme (Light, Dark, Automatic) |
| **API** | `frappe.core.doctype.user.user.switch_theme(theme)` |
| **Boot** | `bootinfo["desk_theme"]` from `sessions.py` |
| **UI** | Theme switcher dialog in navbar |

### Website Theme

| Aspect | Implementation |
| ------ | -------------- |
| **Doctype** | Website Theme |
| **Template** | `frappe/website/doctype/website_theme/website_theme_template.scss` (Jinja) |
| **Variables** | `$primary`, `$dark`, `$body-text-color`, `$body-bg`, `google_font` |
| **Custom** | `custom_scss`, `custom_overrides` fields |
| **Compilation** | `get_scss()` uses Jinja `frappe.render_template()` → Node script |
| **Imports** | `website_theme_scss` from `get_scss_paths()` (website.scss, website.bundle.scss) |

### Theme Override Hooks

- `website_theme_scss` in hooks: add SCSS import paths for Website Theme.

---

## 12. UI Component Framework

| Component Type | File Location | Framework |
| -------------- | ------------- | --------- |
| Form controls | frappe/public/js/frappe/form/ | Vanilla JS (frappe-control) |
| List view | frappe/public/js/frappe/views/list/ | Vanilla JS |
| Form view | frappe/public/js/frappe/views/form/ | Vanilla JS |
| Report view | frappe/public/js/frappe/views/report/ | Vanilla JS |
| Kanban | frappe/public/js/frappe/views/kanban/ | Vue |
| Calendar | frappe/public/js/frappe/views/calendar/ | FullCalendar |
| Modals | frappe/public/js/frappe/ui/dialog.js | jQuery + Bootstrap |
| Toolbar | frappe/public/js/frappe/ui/toolbar.js | Vanilla JS |
| Web templates | frappe/public/js/frappe/utils/web_template.js | Vue |
| Print format builder | frappe/public/js/print_format_builder/ | Vue |

---

## 13. How Styles Are Loaded in the App

### Desk (SPA)

1. `desk.py` builds `app_include_css` from hooks + site config.
2. `desk.html` loops: `{% for include in app_include_css %}{{ include_style(include) }}{% endfor %}`.
3. `include_style(path)` in `jinja_globals.py` calls `bundled_asset(path)`.
4. `bundled_asset()` looks up `path` (e.g. `desk.bundle.css`) in `assets.json` → hashed URL.
5. Output: `<link rel="stylesheet" href="/assets/frappe/dist/css/desk.bundle.ABC123.css">`.
6. Icons exist in hooks.py (`app_include_icons`) and loaded using `include_icons()` macro on `desk.html`

### Website

1. `head.html` includes `include_style('website.bundle.css')` and `web_include_css` links.
2. Website Theme CSS is linked separately via `theme_url` when a theme is active.

### Asset Resolution

- **File:** `frappe/utils/jinja_globals.py`
- **Function:** `bundled_asset(path)` → reads `frappe.utils.get_assets_json()`.
- **RTL:** For RTL languages, `rtl_desk.bundle.css` is used when available.

---

## 14. Override Mechanisms

| Override Method | File | How It Works | Stability |
| --------------- | ---- | ------------- | --------- |
| **app_include_css** | hooks.py, site_config | Append CSS bundles to Desk; merged in desk.py | Stable |
| **app_include_js** | hooks.py, site_config | Append JS bundles to Desk | Stable |
| **app_include_icons** | hooks.py, site_config | Append icons.svg to Desk | Stable |
| **web_include_css** | hooks.py | Append CSS to website head | Stable |
| **web_include_js** | hooks.py | Append JS to website | Stable |
| **Website Theme** | Website Theme doctype | Custom SCSS, colors, fonts; compiles to CSS | Stable |
| **website_theme_scss** | hooks.py | Add SCSS imports to Website Theme | Stable |
| **Custom app public/** | Your app | Add `*.bundle.scss` or `*.bundle.js`; register in hooks | Stable |
| **Variable override** | Your SCSS | Override `:root` or `[data-theme="dark"]` after imports | Medium |
| **Patch core SCSS** | Not recommended | Direct edits to frappe/public/scss | Fragile |

### Hook Examples

```python
# In your app's hooks.py
app_include_css = ["your_app.bundle.css"]
app_include_js = ["your_app.bundle.js"]
web_include_css = ["your_website.css"]
website_theme_scss = ["your_app/public/scss/website_theme.scss"]
```

---

## 15. Safe Override Strategy

### Recommended Approaches

1. **Custom app bundle**
   - Create `your_app/public/scss/your_app.bundle.scss` importing Frappe variables.
   - Add to `app_include_css` in hooks.
   - Override only the variables/components you need.

2. **Variable overrides**
   - In your bundle, after `@import` of Frappe SCSS (if needed), add:
   ```scss
   :root, [data-theme="light"] {
     --btn-primary: #your-color;
     --border-radius: 12px;
   }
   [data-theme="dark"] {
     --btn-primary: #your-dark-color;
   }
   ```

3. **Component overrides**
   - Use higher-specificity selectors or load your CSS after Frappe's.
   - Prefer overriding CSS variables over hardcoding values.

4. **Website Theme**
   - Use Website Theme doctype for website-only changes.
   - Use `custom_scss` and `custom_overrides` for small tweaks.

### Avoid

- Editing `frappe/public/scss/*` directly.
- Relying on internal class names that may change.
- Inline styles or JS-driven styles for design tokens.

---

## 16. Update Compatibility Risks

| Risk Area | Description |
| --------- | ----------- |
| **Compiled CSS** | Hashed filenames change on build; use `bundled_asset()` / `include_style()` |
| **Bootstrap upgrade** | Variable names/structure may change |
| **Espresso tokens** | New tokens or renames in `_colors.scss`, etc. |
| **Dark mode** | dark.scss overrides may need updates |
| **JS-driven styles** | Inline styles in Vue/JS components |
| **Component structure** | DOM structure changes break selectors |
| **Website Theme template** | Jinja template changes in website_theme_template.scss |

---

## 17. Complete File Map

| Category | File | Relative Path |
| -------- | ---- | ------------- |
| **Build** | esbuild.js | `esbuild/esbuild.js` |
| **Build** | sass_options.js | `esbuild/sass_options.js` |
| **Build** | build.py | `frappe/build.py` |
| **Build** | package.json | `package.json` |
| **Desk bundle** | desk.bundle.scss | `frappe/public/scss/desk.bundle.scss` |
| **Desk index** | index.scss | `frappe/public/scss/desk/index.scss` |
| **Desk vars** | variables.scss | `frappe/public/scss/desk/variables.scss` |
| **Desk vars** | css_variables.scss | `frappe/public/scss/desk/css_variables.scss` |
| **Desk dark** | dark.scss | `frappe/public/scss/desk/dark.scss` |
| **Desk typography** | typography.scss | `frappe/public/scss/desk/typography.scss` |
| **Common vars** | css_variables.scss | `frappe/public/scss/common/css_variables.scss` |
| **Common** | mixins.scss | `frappe/public/scss/common/mixins.scss` |
| **Common** | buttons.scss | `frappe/public/scss/common/buttons.scss` |
| **Common** | form.scss | `frappe/public/scss/common/form.scss` |
| **Common** | controls.scss | `frappe/public/scss/common/controls.scss` |
| **Common** | modal.scss | `frappe/public/scss/common/modal.scss` |
| **Common** | alert.scss | `frappe/public/scss/common/alert.scss` |
| **Espresso** | _colors.scss | `frappe/public/scss/espresso/_colors.scss` |
| **Espresso** | _typography.scss | `frappe/public/scss/espresso/_typography.scss` |
| **Espresso** | _shadows.scss | `frappe/public/scss/espresso/_shadows.scss` |
| **Espresso** | _borders.scss | `frappe/public/scss/espresso/_borders.scss` |
| **Espresso** | _spacing.scss | `frappe/public/scss/espresso/_spacing.scss` |
| **Website** | website.bundle.scss | `frappe/public/scss/website.bundle.scss` |
| **Website** | index.scss | `frappe/public/scss/website/index.scss` |
| **Website** | variables.scss | `frappe/public/scss/website/variables.scss` |
| **Theme** | website_theme_template.scss | `frappe/website/doctype/website_theme/website_theme_template.scss` |
| **Theme** | website_theme.py | `frappe/website/doctype/website_theme/website_theme.py` |
| **Desk template** | desk.html | `frappe/www/desk.html` |
| **Desk context** | desk.py | `frappe/www/desk.py` |
| **Asset resolution** | jinja_globals.py | `frappe/utils/jinja_globals.py` |
| **Theme switcher** | theme_switcher.js | `frappe/public/js/frappe/ui/theme_switcher.js` |
| **Hooks** | hooks.py | `frappe/hooks.py` |

---

*Document generated for Frappe Framework. Use this as a reference when overriding or replacing the design system.*

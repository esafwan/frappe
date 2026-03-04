# The Ultimate Guide to Overriding the Frappe Theme

If you are tasked with making Frappe look like a fundamentally different application (e.g., Gmail, Outlook, or a custom enterprise design system), this guide provides the definitive, step-by-step approach. 

The core principle is **override, do not edit**. You should never modify core Frappe SCSS files directly. Instead, you will build a parallel SCSS structure in a custom Frappe app and inject it via hooks.

---

## Step 1: Set Up the Custom App Injection

First, create a custom Frappe application to house your theme.

1. **Create the app:** `bench new-app my_theme_app`
2. **Install to site:** `bench --site yoursite.localhost install-app my_theme_app`

### The Critical Hooks
In your custom app's `hooks.py`, you instruct Frappe to load your CSS and icons *after* its own.

```python
# my_theme_app/hooks.py

# 1. Inject Desk UI overrides (SPA)
app_include_css = ["my_theme_app.bundle.css"]

# 2. Inject custom Icons (Optional but recommended for complete reskins)
app_include_icons = ["my_theme_app/public/icons.svg"]

# 3. Inject Public Website overrides (Optional)
web_include_css = ["my_theme_web.bundle.css"]
```

---

## Step 2: Architecture of Your Styles

Create your SCSS entry point: `my_theme_app/public/scss/my_theme_app.bundle.scss`. 

For a massive reskin, structure your SCSS to mirror the components you are overriding:

```text
my_theme_app/public/scss/
├── my_theme_app.bundle.scss   # The main entry point
├── _variables.scss            # Your new design tokens
├── components/
│   ├── _navbar.scss           # Overriding Desk top bar
│   ├── _sidebar.scss          # Overriding the left menu
│   ├── _cards.scss            # Overriding dashboard metrics
│   ├── _forms.scss            # Overriding form inputs & layouts
│   └── _buttons.scss          # Overriding button styles
└── _dark_mode.scss            # Your dark mode overrides
```

### `my_theme_app.bundle.scss`
Your entry file should look like this:

```scss
// 1. Import your custom variables (if you need SASS variables)
@import "variables";

// 2. Override CSS native variables globally
:root, [data-theme="light"] {
    /* Base Espresso Tokens */
    --primary: #1a73e8; /* Gmail Blue */
    --gray-50: #f8f9fa;
    --gray-900: #202124;
    
    /* Layout Variables */
    --navbar-height: 56px;
    --page-max-width: 1200px;
    --border-radius: 8px;
    --border-radius-sm: 4px;
    --card-shadow: 0 1px 2px 0 rgba(60,64,67,0.3), 0 1px 3px 1px rgba(60,64,67,0.15);
    
    /* Component Variables */
    --btn-primary: var(--primary);
    --control-bg: #ffffff;
    --input-height: 36px;
}

// 3. Import component overrides
@import "components/navbar";
@import "components/sidebar";
@import "components/cards";
@import "components/forms";
@import "components/buttons";

// 4. Import Dark Mode
@import "dark_mode";
```

---

## Step 3: Overriding the Core Design Tokens

Frappe relies heavily on native CSS variables (Custom Properties). Because your CSS bundle is loaded *after* Frappe's, redefining these variables in your `:root` block instantly changes the look of hundreds of components.

### 1. Color Palette (Espresso Tokens)
Frappe uses a strict gray scale (`--gray-50` to `--gray-900`) and semantic colors (`--blue-*`, `--red-*`, etc.). Override these to match your brand. For a Gmail-like look, you might make `--gray-50` (page background) totally white and `--gray-100` slightly darker for input fields.

### 2. Spacing & Sizing
Frappe's default densities can be compact. You can open them up:
```scss
:root, [data-theme="light"] {
    --padding-sm: 12px;
    --margin-sm: 16px;
    --input-padding: 8px 12px;
}
```

### 3. Typography
To change the system font, override `--font-stack`:
```scss
:root, [data-theme="light"] {
    --font-stack: 'Google Sans', 'Roboto', 'Helvetica Neue', sans-serif;
}
```
*(Make sure to `@import` your font in the entry file).*

---

## Step 4: Overriding Specific Components

Variable overrides alone won't achieve custom layouts (e.g., transforming the Frappe sidebar to look like Outlook's vertical tab bar). You need CSS structural overrides.

### Tips for Structural Overrides
1. **Specificity is Key:** Since your CSS loads last, a selector of equal weight to Frappe's will win. E.g., `.form-control` in your file overrides `.form-control` in Frappe.
2. **Avoid `!important`:** Try to match or slightly exceed Frappe's specificity (e.g., `.frappe-control .form-control` instead of `.form-control !important`).

### Example 1: Reskinning Inputs (Gmail Style)
```scss
// _forms.scss
.frappe-control {
    .form-control {
        border: 1px solid var(--gray-300);
        &:focus {
            border: 2px solid var(--primary);
            box-shadow: none; /* Remove Frappe's default glow */
            padding-left: 11px; /* Adjust padding for 2px border jump */
        }
    }
}
```

### Example 2: Reskinning the Navbar
```scss
// _navbar.scss
.navbar {
    background-color: var(--primary); /* Blue header */
    box-shadow: var(--shadow-sm);
    
    /* Make navbar items white */
    .navbar-nav .nav-link {
        color: white;
        &:hover {
            color: rgba(255,255,255,0.8);
        }
    }
}
```

### Example 3: List Views / Tables
Frappe uses a flexbox grid system for lists (not HTML `<table>`).
```scss
.list-row {
    border-bottom: 1px solid var(--border-color);
    transition: background-color 0.2s;
    
    &:hover {
        background-color: var(--gray-50);
        box-shadow: var(--shadow-xs);
        z-index: 1; /* Pop out slightly */
    }
}
```

---

## Step 5: Overriding Dark Mode

Frappe limits dark mode styling to the `[data-theme="dark"]` selector. You must replicate this for your overrides to ensure dark mode works seamlessly.

```scss
// _dark_mode.scss
[data-theme="dark"] {
    /* 1. Override the baseline colors */
    --primary: #8ab4f8; /* Lighter blue for dark backgrounds */
    --bg-color: #202124; /* Google Dark Gray */
    --control-bg: #303134; 
    
    /* 2. Specific Component Tweaks for Dark Mode */
    .navbar {
        background-color: #202124;
        border-bottom: 1px solid #5f6368;
    }
    
    .list-row:hover {
        background-color: #303134;
    }
}
```

---

## Step 6: Custom Icons

If you want to use custom SVG icons instead of Frappe's default SVGs:

1. Create a sprite file: `my_theme_app/public/icons.svg`
2. Add `<symbol id="icon-name">...</symbol>` blocks inside.
3. Because you added `app_include_icons` in `hooks.py`, Frappe will inject your SVG sprite map into the DOM.
4. If your `id` matches a Frappe default icon (e.g., `<symbol id="icon-search">`), your icon will completely replace Frappe's throughout the application.

---

## Step 7: The Production Build

When you are ready to see your changes (or deploy):

```bash
# During development (watches for changes and recompiles instantly)
# Warning: Do this from the bench directory
bench watch

# For production deployment
bench build --apps my_theme_app
```

Frappe will process your `.bundle.scss` via `esbuild`, minify it, resolve paths, and link it via `assets.json` so it effortlessly cache-busts on updates.

---

## Final Checklist for a Complete Reskin

1. [ ] **`hooks.py` configured** with `app_include_css`.
2. [ ] **Global CSS variables overridden** (colors, padding, borders).
3. [ ] **Typography updated** (Font family imported and assigned to `--font-stack`).
4. [ ] **Navbar and Sidebar structural CSS applied.**
5. [ ] **Form inputs styled** targeting `.frappe-control` and `.form-control`.
6. [ ] **Buttons styled** targeting `.btn` and `.btn-primary`.
7. [ ] **List/Grid Views styled** targeting `.list-row` and `.grid-body`.
8. [ ] **Dark mode tested** by toggling the theme switcher; `--bg-color` and `--control-bg` adjusted inside `[data-theme="dark"]`.
9. [ ] **Custom SVG icons injected** via `app_include_icons`.

By following this architecture, 100% of your graphical changes remain inside your custom app, keeping Frappe itself completely upgrade-safe.

## Assistant Potager UI — conventions

This is the design system of a French gardening-tracker web app ("Assistant Potager"), refonte 2026. Read `styles.css` (its `@import` closure, which reaches `_ds_bundle.css`) before styling anything — it is the single source of truth for every token and utility class named below.

### Setup

No provider/root wrapper is required — components read no React context. Dark mode is a plain CSS class toggle: wrap the app root in `.dark` to switch every semantic color token to its dark value (`<div className="dark">…</div>`). Do not build a theme manually — just add/remove the class.

### Styling idiom: Tailwind utilities over semantic color tokens

This DS never uses raw Tailwind palette colors (`bg-green-600`, `text-gray-500`, …) or arbitrary hex values in class names. Every color is one of these semantic utility classes (backed by a CSS custom property that flips value in `.dark`):

| Role | Classes |
|---|---|
| Surfaces | `bg-bg`, `bg-surface`, `bg-card`, `bg-card-alt` |
| Borders | `border-border`, `border-border-soft` |
| Brand | `bg-brand`, `text-brand`, `text-brand-deep`, `bg-brand-soft`, `text-brand-text` |
| Text | `text-txt` (primary), `text-txt2` (secondary), `text-txt3` (tertiary/muted) |
| Status accents | `amber`/`amber-soft`, `red`/`red-soft`, `blue`/`blue-soft`, `violet`/`violet-soft` — each as `bg-*-soft` (tinted background) + `text-*` (icon/text); these are not used as `border-*` in this codebase |
| Header (on the brand gradient bar) | `bg-header-glass`, `text-header-txt`, `text-header-dim` as utility classes; `--header-from`/`--header-to` as CSS custom properties consumed via inline `style={{background: 'linear-gradient(…, var(--header-from), var(--header-to))'}}`, never as Tailwind classes |

Ignore any `g-*`-prefixed color (`g-bg`, `g-acc`, `g-pri`, …) — those are legacy compatibility aliases for screens not yet migrated; never use them in new compositions.

Typography: `font-serif` (Lora — headings, emphasis) and `font-sans` (system stack — body text). Card elevation: `shadow-card` (never a raw `shadow-*` Tailwind utility). Radii run large and soft — components use custom values like `rounded-[10px]`/`rounded-[18px]`, not the default Tailwind scale.

### Responsive components: container queries, not screen breakpoints

Every component in this DS is meant to render correctly at any width inside any layout. New reusable compositions should size/adapt via `@container` queries (`@container/name (min-width: …)`) on a wrapper with `container-type: inline-size` — never `md:`/`lg:` screen breakpoints, which this codebase reserves exclusively for top-level page structure (sidebar vs. bottom-nav). A composition using `@container` will look right whether it lands in a narrow card or a wide panel.

### Components

23 components, all in the `general` group (this is a small, flat kit — don't invent subgroups). Composition patterns worth knowing:
- `Card` + `CardHead` compose together (head is a named slot, not a prop).
- `Pop` is the base dropdown/menu primitive; `PopHead`, `PopItem`, `PopSep` are its children. `RoleSelect` shows the real composed pattern (button trigger + `Pop` panel + `PopItem`-style rows).
- `Modal` takes `title`, optional `icon` (a component reference, e.g. a lucide-react icon), optional `sub`/`foot`, and `onClose`.
- `Btn` has 4 `kind`s: `primary`, `ghost` (default), `soft`, `quiet`; pass `icon` as a component reference, and `small` for the compact size.
- Icons throughout are `lucide-react` components passed by reference (`icon={Pencil}`), never pre-rendered elements.

### Where the truth lives

`styles.css` → `_ds_bundle.css` (all tokens + utilities, light and dark). Per-component API: `components/general/<Name>/<Name>.d.ts` and `<Name>.prompt.md`.

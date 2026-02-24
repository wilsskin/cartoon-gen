# Design System - CartoonGen

This document defines the rules we follow so a new contributor can implement UI consistently. Follow the overarching rules; the listed exceptions are the only cases where we break them.

---

## Typography

**Rule:** We use two typefaces only: **Crimson Pro** for display/titles and **Crimson Text** for all body text, labels, and UI. Load only these two fonts (no Roboto or others).

**Type scale:** Use only **11px**, **16px**, **20px**, and **36px**.
- **36px** — Hero / main brand title (Crimson Pro).
- **20px** — Headlines, section titles (h2s), subtitles (Crimson Text).
- **16px** — Body, meta, footer, filter, buttons, back link, error text.
- **11px** — Tooltips only.

**Exception:** Tooltips use the **system font stack** (not Crimson) at 11px for legibility. This is the only place we deviate from Crimson Pro / Crimson Text.

**Letter-spacing:** 16px text uses none (default). Headlines (20px) use slightly tighter (-0.015em to -0.03em); 36px display uses -0.04em.

**Line-height:** Headlines 1.2 (or 1.15 where tighter); body 1.33.

---

## Colors

**Rule:** Keep the palette small. Prefer primary black (#000000), secondary gray (#767676), and white (#FFFFFF) with our standard borders and hovers.

**Text:** Primary #000000. Secondary/meta #767676. **Exception:** Headline hover uses #727272 so it’s distinct from static secondary text.

**Backgrounds:** Default #FFFFFF. Hover and subtle surfaces #f5f5f5 (buttons, filter options, error state backgrounds). **Exception:** Tooltip background is #1a1a1a (dark); tooltip text is white.

**Borders:** Subtle `rgba(118, 118, 118, 0.15)`; dividers and stronger outlines `rgba(118, 118, 118, 0.3)`.

**Semantic:** Error text and error borders stay **#d32f2f**. Error and global-error backgrounds use **#f5f5f5** (gray), not yellow.

**Overlays:** Two only — (1) **Modal backdrop:** `rgba(0, 0, 0, 0.2)` for lightbox/gallery; (2) **Button hover:** `rgba(0, 0, 0, 0.05)` for icon buttons. Use these consistently; any new overlay should match one of these or be documented here.

---

## Spacing & layout

**Rule:** 8px grid — use 4, 8, 12, 16, 24, 32, 48, 72, 80 as needed. No need to document every value; stay on the grid.

**Content width:** 576px max-width, centered (header, landing, generation).

**Breakpoint:** At 576px and below, side padding goes from 48px to 24px. Use this single breakpoint for layout and padding changes.

---

## Border radius & shadows

**Rule:** Border radius is **4px** (small elements) or **8px** (cards, buttons, modals, inputs). **Exception:** Circular icon buttons (e.g. gallery prev/next) use **50%**; otherwise prefer 4 or 8.

**Shadows:** Use one elevation style for dropdowns and floating UI: `0 4px 20px rgba(0, 0, 0, 0.12)`. Keep other shadows in the same family (soft, subtle).

---

## Buttons & links

**Rule:** Button hover uses design-system colors: background **#f5f5f5** for text/rect buttons, or overlay **rgba(0, 0, 0, 0.05)** for icon-only buttons. Transitions: **150ms** with **cubic-bezier(0.25, 0.1, 0.25, 1)**.

**Links:** Default inherits (e.g. secondary gray in footer). Hover: opacity 0.8 or color #000000. Footer links explicitly go to #000 on hover.

---

## Animation

**Rule:** Default easing **cubic-bezier(0.25, 0.1, 0.25, 1)** for hover, content, and loading. **Exception:** Dropdown/entrance animations use **cubic-bezier(0.16, 1, 0.3, 1)** at **0.2s** (e.g. filter dropdown).

**Durations:** 100ms (quick feedback), 150ms (hover), 200ms (dropdown open), 400–500ms (content slide-in), 2s (loading). Stagger list entrances by 100ms per item. Keep motion subtle and consistent.

---

## Icons & assets

**Rule:** Use the sizes below so icons and images stay proportional to body text. **Inline-with-text rule:** Icons or logos that sit next to 16px body text use the **16∶14 scale**—multiply any size that was designed for 14px text by (16/14) so they align visually with 16px (e.g. filter icon 18×18, filter dropdown logos 18×14, news source logos 21×16, more/less arrow 11×13).

| Size | Use |
|------|-----|
| **18×18** | Filter icon (landing, next to “Filter” label) |
| **18×14** | Filter dropdown option logos (next to source name) |
| **21×16** | News item source logos (next to category/source in headline list) |
| **11×13** | More / Less arrow (landing, next to button text) |
| **16×16** | Back arrow (generation page) |
| **24** | Header logo height |
| **26×20** | Generation page source logo (above headline) |
| **20×20** | Gallery close button (container); 24px icon inside |
| **40×40** | Generation action buttons (desktop) |
| **44×44** | Gallery prev/next circular buttons |
| **48×48** | Generation action buttons on mobile (576px and below) |

**Exception:** On mobile (576px and below), generation action buttons increase to **48×48** with **16px** gap for touch targets.

---

## Accessibility & responsive

**Rule:** Use visible focus states (e.g. focus-visible). Don’t rely on color alone for errors (use text/icon too).

**Responsive:** At 576px and below, generation-page action buttons (download, copy, regenerate) are **48px** with **16px** gap. A separate **600px** breakpoint is used for the hero gallery modal (arrows overlay, close icon and arrow styling). Document any new breakpoint or size change here.

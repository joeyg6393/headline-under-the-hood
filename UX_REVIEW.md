# UI/UX Review — Headline Under The Hood

Reviewed: dashboard (`/`) and report deep-dive (`/reports/{id}`) at three widths — 1440 (desktop), 820 (tablet), 390 (mobile) — using a seeded set of 14 demo reports. Screenshots saved under the project's outputs folder.

A standalone HTML mockup of the proposed redesign lives at `mockup/redesign.html` and renders in any browser without a server.

---

## Headline issues, ranked

### 1. The narrow-viewport stacking buries the content. *(critical, responsive)*
On tablet and mobile, `.terminal-grid` stacks `side-rail → feed → detail`. The side-rail is filters + calendar + the entire "New analysis" form, so a first-time visitor on a phone scrolls past ~1500px of inputs and selects before reaching a single release card. The form is a power-user utility; the feed is the product.

**Fix:** under 980px, render the feed first, hide the form behind a floating "+ Analyze" button that opens a bottom sheet (or a `<details>` collapsible). Filters can collapse into a single "Filter" button that opens a small sheet as well. Detail panel opens as a slide-over rather than a third stack item.

### 2. There is no primary action — every button looks the same. *(high, hierarchy)*
The topbar has *Seed examples / Run demo / Refresh* — three identical solid-teal buttons. Two of those are developer conveniences. Inside cards, "View full analysis" is also styled as a primary chip. The user has no visual answer to "what's the main thing I should do here?"

**Fix:** keep one primary style (filled accent) for *Analyze* / *View full analysis*. Demote *Refresh* to a ghost icon button. Move *Seed examples* + *Run demo* into a small overflow menu (`⋯`) — they are demo-only.

### 3. The score has no visual scale. *(high, comprehension)*
A standalone `60` in a colored badge tells you nothing about where 60 sits in the 0–100 range, or how it relates to the verdict thresholds (45 / 75). The semantic color is the only cue and color-blind users get nothing.

**Fix:** render the score as a circular gauge (SVG `stroke-dasharray`) with the number in the middle. Add a tiny tick at 45 and 75 so the threshold is legible at a glance. Mini-cards on the feed get a horizontal bar version of the same.

### 4. The h1 + eyebrow pairing is inverted. *(medium, hierarchy)*
"Headline Under The Hood" at 28–42px isn't useful information for the user once they're on the page — they already know what app they're in. The actually-informational bit (count of reports, latest release date, average score) is squeezed below in the ticker strip with much smaller type.

**Fix:** shrink the brand to a small logo + wordmark in the topbar (16–18px). Promote the ticker stats to be the page's actual headline — a row of large, monospaced numbers with sparklines. That's the "vibes check" a user wants on landing.

### 5. "Same scorecard" eyebrow on the report page is confusing. *(low, copy)*
Reads like a draft note. Same with `Status` field rendering as the literal string `complete` in the eyebrow line on the dashboard detail panel.

**Fix:** drop the "Same scorecard" eyebrow entirely (the section heading "Report Scorecard" is enough). Remove the status string from the eyebrow unless it's `pending` (then surface it prominently as a banner).

### 6. Empty / pending states render as bare text. *(medium, polish)*
"No score components yet." and "Analysis is pending. Refresh shortly." sit alone in white panels with no iconography or call to action. The empty Concrete Math block on the report I sampled looks broken at first glance.

**Fix:** add a small icon + secondary action ("Re-run analysis", "Open raw report"). For pending state, show a thin animated progress line.

### 7. Card density is high and uniform — nothing pops. *(medium, hierarchy)*
Each card is: source chip + type chip + date + score + h3 + headline + blurb + 3×2 metric grid + verdict + CTA. Eyes don't know where to land first.

**Fix:** anchor the card on a left-aligned score block (gauge + verdict word like "Strong"/"Mixed"). Push the metric grid to a hover/expand state, or shrink it to 4 micro-tiles inline. Use weight contrast: bold the headline, demote everything else to muted.

### 8. The "Calendar" rail isn't a calendar. *(low, naming)*
It's a list of dates with counts. Either rename it ("Recent dates") or actually render a small month-grid heatmap (cells colored by score average for that day's releases). The latter would be a much more useful dashboard widget.

### 9. Filters are basic native selects. *(low, density)*
Source has 2–3 values typically (BLS / BEA / Fed / etc.). Three native dropdowns in stacked rows is heavier than a row of 3–4 segmented chips would be.

**Fix:** segmented control for *Source*, keep type as a select (more values), keep month as a select.

### 10. No dark mode. *(low, expectation)*
Financial-data UIs are almost universally dark-mode-capable. The current palette is light-only and there's no toggle. Adding a `prefers-color-scheme` block + a toggle in the topbar is ~50 lines of CSS — high value for the effort.

### 11. Compact accessibility wins still on the table. *(medium, a11y)*
- `aria-live` on `#feedCount` and `#formStatus` so screen readers hear updates.
- `<button>` cards in the feed are `<article>` with click handlers — should be either real buttons or `role="button"` with `tabindex="0"` + key handler.
- Score-badge color contrast is fine in good/bad but `.mixed` (warn-soft / warn) measures around 3.4:1 — under WCAG AA for small text. Bumping `--warn` to `#7a4f12` fixes it.
- The textarea has no character count or word-count hint, even though the analyzer behaves differently with long vs short reports.

### 12. Numeric type isn't tabular. *(low, polish)*
Scores, dates, and metric values are rendered in Inter's proportional digits, so columns of numbers don't align. Adding `font-variant-numeric: tabular-nums` to ticker, scorecard tiles, and metric rows is a one-liner that gives the whole UI a much more "data-product" feel.

---

## Responsive specifics

| Width | Current behavior | Recommended |
|-------|------------------|-------------|
| ≥1220 | 3-col grid, sticky panes | Keep, but raise feed-column min to 1fr 2fr 1fr (feed is the star) |
| 981–1220 | Squeezes to 230/1fr/300 | Same shape, but cards collapse mini-grid below 1100 |
| 821–980 | 2-col (rail + feed), detail dropped below | Switch to single-column feed, detail opens as overlay |
| 541–820 | All blocks stack, form first | Feed first, filter/form behind buttons |
| ≤540 | Full-width, buttons stretch | Bottom sheet for filters, FAB for analyze |
| ≤360 | Single-column micro-tiles | Same; ensure score gauge stays 64px |

The current breakpoint chain (`1220 / 980 / 820 / 540 / 360`) is sound — the issue is *what* gets done at each break, not *where* the breaks live.

---

## Quick wins (≤30 minutes each)

1. Add `font-variant-numeric: tabular-nums` to ticker / scorecard / metric values.
2. Remove "Same scorecard" eyebrow.
3. Promote ticker numbers from 20px to 28–32px.
4. Demote *Refresh* and *Seed examples* to ghost / icon-only styling.
5. Add `prefers-color-scheme: dark` block.
6. Wrap each release card in a real `<button>` (or add proper keyboard handling).
7. Bump `--warn` to a darker shade for AA contrast.
8. Add an icon to the search input.

## Bigger lifts

1. Score gauge component (replaces flat badges everywhere).
2. Move "New analysis" out of the side rail into a modal/sheet.
3. Replace date list with an actual calendar heatmap.
4. Slide-over detail panel on tablet.
5. Sparklines in ticker stats (last N scores, last N count of mixed/weak).

---

## Mockup

A standalone HTML file — `mockup/redesign.html` — implements most of the recommendations above (gauge, hierarchy, dark mode, responsive bottom-sheet, segmented filter, calendar heatmap). Open it directly in a browser; it has no dependencies and uses inline mock data so you can resize the window to see the responsive behavior.

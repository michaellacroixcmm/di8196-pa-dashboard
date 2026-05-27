# Pharmacy Platform Intelligence Dashboard — Session Notes

> Last updated: 2026-05-27

---

## How to run

```bash
cd "/Users/michael.lacroix/AI_efforts/DI-8196_Mock Tableau"
source ../.venv/bin/activate    # ← required; Flask lives in the parent venv
python3 app.py
# → http://localhost:5001
```

---

## File map

| File | Purpose |
|---|---|
| `app.py` | Flask backend — data loading, filtering, aggregation, API routes |
| `templates/index.html` | Entire frontend — all HTML, CSS, and JS inline, no separate static files |
| `test_platform_dataset_size_example_v5.csv` | Sample dataset (~10K rows, Apr 2025–Apr 2026). Real dataset is much larger |
| `CoverMyMeds_Logo.png` | Logo served via `/logo` route, embedded in header |
| `branding guide.pdf` | Source of truth for brand colors (pixel-sampled) |
| `Overview - Volume.pdf` | Tableau reference — single-series view |
| `Overview - Volume with Breakouts.pdf` | Tableau reference — stacked breakout view |
| `SESSION_NOTES.md` | This file |

---

## Dataset columns (key ones)

| Column | Description |
|---|---|
| `created_month` | YYYY-MM-01, used as x-axis |
| `request_id_count` | PA count — the main metric |
| `accessed_online`, `sent_to_plan`, `approved` | Numerators for the three rate KPIs |
| `gross_revenue` | Revenue KPI |
| `real` | "Real" / "Not Real" |
| `is_epa` | "Classic" / "ePA" |
| `sponsored` | "Sponsored" / "Not Sponsored" |
| `account_name`, `drug_name`, `drug_group`, `plan_name` | High-cardinality dimensions |
| `state`, `revenue_source`, `pa_start_type`, `reject_code_clean` | Filter and breakout dimensions |
| `line_of_business`, `Generic_DDID_Flag`, `multisource`, `otc_flag` | Additional filter dimensions |

---

## Architecture

### Backend (`app.py`)

- Loads CSV into a pandas DataFrame on startup
- `FILTER_MAP` (17 entries) — maps URL params to column names for the sidebar filters
- `BREAKOUT_COLS` (10 entries) — maps URL params to column names for chart breakouts
- `apply_filters(data, args)` — applies sidebar filters AND `date_from` / `date_to` date range
- **Routes:**
  - `GET /` — serves the dashboard
  - `GET /logo` — serves `CoverMyMeds_Logo.png`
  - `GET /api/filters` — returns unique values per filter dimension + available `months` list
  - `GET /api/data` — returns KPIs, chart datasets, table rows, and `total_series` count

### Frontend (`templates/index.html`)

- CDNs: Chart.js 4.4.0 + chartjs-plugin-datalabels 2.2.0
- `appState` — holds active filter selections and breakout
- `buildQS()` — assembles the full query string (filters + breakout + top_n + date range)
- `loadData()` → `updateDashboard()` → updates KPIs, chart, color key, table, series count

---

## Features

### Header
- CoverMyMeds logo (served from `/logo`)
- Multi-color divider stripe matching CMM brand (magenta → blue → orange → navy)
- Title: **Pharmacy Platform Intelligence**
- Description text
- "Do not share externally" warning in CMM magenta
- KPI tiles: **Total PA Volume** and **Total Gross Revenue** (orange values, orange border)

### Left sidebar (196px, orange left border)
17 multi-select filter dropdowns — each opens a fixed-position checkbox list attached to `<body>` to avoid z-index clipping:

> Pharmacy Account · System Vendor · Revenue Source · PA Start Type · Is Sponsored PA · Is Real · Is Epa · Reject Code - Order · Rejection Code · State · Line Of Business
>
> **Drug Breakdown:** DDID & Drug Name · Drug Group · Plan Name · Generic DDID Flag · Multisource · Is OTC

Red ✕ button clears all filters at once.

### Section header band
- "High Level Summary of PA Requests / Pharmacy Initiated"
- Orange left border, warm cream background
- **IPA Volume** KPI on the right (orange)

### Selected filters bar
Shows current Account / API Client / Reject Code selections inline.

### Rate KPI tiles (3, centered)
- **Physician Access Rate** — accessed / total PAs
- **Sent to Plan Rate** — sent / total PAs
- **Approval Rate** — approved / total PAs

Each shows the large % in CMM orange, label in navy, detail text below.

### Bar chart
- Height: 345px · Max-width: 1050px
- `barPercentage: 0.85`, `categoryPercentage: 0.88` — wide, close-together bars
- **Total mode** — single CMM orange bar; value label above each bar
- **Breakout mode** — stacked colored segments:
  - Each segment shows its value **centered inside** (white bold text, dark pill background)
  - Segments < 4% of bar height are suppressed (via `formatter` returning `null`)
  - Stack grand total floats **above** the topmost segment (offset 18px)

### Date range filter (below chart)
- From / To month dropdowns, populated from `api/filters` months list
- Warm cream bar with orange top/bottom borders
- Filters **everything** — KPIs, chart, and table all respond
- Reset button (magenta outline) → snaps back to full range

### Breakout radio buttons (11 options)
Is Total · Is ePA · Is Sponsored PA · Is Real · State · Revenue Source · PA Start Type · Reject Code · Account Name · Plan Name · Drug Name

**Color key** — appears below the radio buttons when any non-total breakout is active; wraps and scrolls up to 130px tall.

**Top N selector** — appears for all breakouts (hidden for Is Total):
- High-cardinality breakouts (State, Reject Code, Account, Plan Name, Drug Name) default to **Top 20**
- Low-cardinality breakouts default to **All**
- Dropdown: Top 20 · Top 50 · All
- Shows count: "(showing 20 of 3,294)"

### Breakdown table
- Sortable — click any month column header or Grand Total to sort ↑ ↓; active column highlighted in magenta
- **Grand Total** column always on the far right (CMM orange background)
- Navy header row, warm cream alternating rows, CMM orange Grand Total column
- **⬇ Export CSV** button (top-right of table) — exports current view (filters + breakout + sort) as `pa_volume_<breakout>_<date>.csv`

---

## CoverMyMeds branding

Colors pixel-sampled directly from `branding guide.pdf` and `CoverMyMeds_Logo.png`:

| Token | Hex | Used for |
|---|---|---|
| CMM Orange | `#ff8f1c` | KPI values, chart bars (total), section accents, Grand Total column, export button |
| CMM Magenta | `#eb0768` | Warning text, clear button, active sort column, reset button |
| CMM Navy | `#01426a` | Headings, table headers, filter labels, rate KPI labels |
| CMM Blue | `#1e91d5` | Header stripe, chart palette |
| CMM Cream | `#fff1eb` | Outer page background |
| Body text | `#565656` | General text |

**Chart PREDEFINED_COLORS:**
- `is_epa`: Classic = `#01426a`, ePA = `#1e91d5`
- `is_sponsored`: Not Sponsored = `#01426a`, Sponsored = `#ff8f1c`
- `is_real`: Real = `#ff8f1c`, Not Real = `#c8bdb8`

**Chart PALETTE** — 20-color array starting with CMM orange, magenta, navy, blue, then tints/variants.

---

## Critical gotchas

### 1. venv activation
Flask is in `../.venv` (parent folder). The server will fail with `ModuleNotFoundError` without activating it first:
```bash
source ../.venv/bin/activate
```

### 2. datalabels `display` callback kills segment labels
The `chartjs-plugin-datalabels` `seg` named label must **not** use a `display` callback — it silently suppresses the label after chart creation. Use `formatter` returning `null` instead:

```js
seg: {
  formatter: (v, ctx) => {
    if (!v || v <= 0) return null;
    const tot = stackTotal(ctx);
    return tot > 0 && v / tot >= 0.04 ? fmtY(v) : null;
  },
  // ← no display callback here
}
```

### 3. Named labels structure must stay consistent
Always mutate `.labels` in place — never replace the whole `datalabels` object:
```js
chart.options.plugins.datalabels.labels = buildLabels(isTotal);
chart.update();
```
Replacing the whole object breaks the plugin's internal references.

### 4. Filter dropdowns appended to `<body>`
Each dropdown div is appended to `document.body` (not inside the sidebar) to avoid `overflow: hidden` clipping. Position is recalculated from `getBoundingClientRect()` on each open.

### 5. CSV file path
`DATA_PATH` in `app.py` line 7 points to `test_platform_dataset_size_example_v5.csv`. Update this when connecting to the real dataset.

---

## Possible next steps

- Connect to a real database or larger CSV
- Responsive layout for smaller screens
- "Other" bucket for Top N (group remaining values rather than dropping them)
- Additional KPI tiles or trend indicators
- User-facing documentation / tooltip help text

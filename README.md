# 123Dentist Careers Kiosk

A single-file HTML kiosk app for displaying 123Dentist job openings at in-person events (e.g. career fairs, conferences). Visitors browse jobs by province → role category → individual listing, then scan a QR code to apply.

---

## Files

| File | Purpose |
|---|---|
| `index.html` | The entire app — styles, HTML structure, job data, and JS logic |
| `update_jobs.py` | Refreshes `RAW_JOBS` from the ADP career center |
| `123Dentist_Logo.png` | Logo shown in header and idle screen |
| `bg.webp` | Background image for the idle screen |
| `smiley.svg` | (Unused or decorative asset) |

No build step, no server, no dependencies beyond two CDN libraries loaded in `<head>`:
- **Google Fonts** — Montserrat
- **qrcodejs** — generates QR codes for job application links

---

## How the app works

The app is a 4-screen flow rendered entirely in JavaScript:

```
Idle Screen → Province → Role Category → Job List → Job Detail
```

1. **Idle screen** — shown on load and after 90 seconds of inactivity. Tap anywhere to start.
2. **Province** (`renderLocation`) — cards for each province that has at least one open job.
3. **Role Category** (`renderCategory`) — cards for each job category within the selected province.
4. **Job List** (`renderJobs`) — all jobs matching the selected province + category.
5. **Job Detail** (`renderJobDetail`) — full detail view with a QR code the visitor scans to apply.

A breadcrumb bar at the top lets users jump back to any step. The "Start Over" button at the bottom always returns to the Province screen.

### Job data structure

All jobs live in a single JavaScript array called `RAW_JOBS` near the top of the `<script>` block (currently around line 520). Each entry looks like:

```js
{
  posting:     10000,
  clinic:      "Victoria Square Dental",
  title:       "Associate Dentist",
  category:    "Associate",
  status:      "Commission",    // see STATUS_LABELS below
  city:        "Regina",
  province:    "SK",
  salary:      "",              // empty string if not listed
  date:        "May 6, 2026",
  description: "<formatted HTML>",
  url:         "https://workforcenow.adp.com/..."
}
```

The app groups jobs automatically by province and category — no manual grouping needed.

### Job description formatting

The `description` field contains formatted HTML generated from the raw ADP description text. The formatter:

- Detects section headers (e.g. `WHAT WE ARE OFFERING`, `WHO WE ARE`, `About the Role`, `What We Offer`, `Schedule`, `Qualifications`, etc.) and renders them as bold uppercase headings.
- Bullet-formats list sections (offerings, requirements, responsibilities, qualifications, benefits).
- Passes paragraph sections (who we are, about us, schedule, compensation) through as plain text.
- Skips any header whose content is empty so no orphaned headings appear.

Each section is wrapped in `<div class="desc-sec">` with a `<div class="desc-body">` for the content. CSS hides the entire section if the body is empty (`.desc-sec:has(.desc-body:empty)`), catching any edge cases the formatter misses.

### Status codes

`status` maps to a human-readable label via `STATUS_LABELS`:

| Code | Display |
|---|---|
| `FT` | Full-Time |
| `PT` | Part-Time |
| `Commission` | Commission |
| `Locum` | Locum |
| `Casual` | Casual |
| `Temp FT` | Temp Full-Time |
| `Temp PT` | Temp Part-Time |

---

## Updating the job listings

`update_jobs.py` reads the public ADP career center (English board, the same board in French, and the separate French career center) and rewrites `RAW_JOBS`. It pages until the number of unique requisitions equals ADP's `totalNumber`. `$top` is ignored on the first page, which returns 19 rows, so a fixed skip of 20 drops a posting. The script overlaps each page and refuses to write a short list.

It keeps every role. Province is taken from each requisition's locations, including a second or third site and a spelled-out province name. Pass `--provinces` to limit the board.

This branch is the New Brunswick and Nova Scotia kiosk. Refresh it with:

```bash
python3 update_jobs.py --provinces NB,NS
```

Omit `--provinces` only when replacing the board with every province. `--dry-run` prints the table and does not edit `index.html`. `--self-test` checks the location parser (Granby, QC must not match New Brunswick).

### Check the board

Open `index.html` directly in a browser. No server needed. Verify:
- The province list shows the expected provinces.
- A few job detail pages load correctly, descriptions are formatted, and the QR code resolves to the right ADP URL.

---

## Analytics

The app sends Google Analytics 4 events via tag `G-X8FG6JMV1R`:

| Event | Fired when |
|---|---|
| `search_started` | Province screen loads |
| `province_selected` | User picks a province |
| `role_type_selected` | User picks a category |
| `job_viewed` | User opens a job detail page |

---

## Kiosk behaviour

- **Idle timeout** — after 90 seconds of no interaction, the app returns to the Province screen and shows the idle overlay. This resets on any touch, click, mouse move, or keypress.
- **Header tap** — tapping the 123Dentist logo in the header also triggers the idle overlay.
- **Responsive** — the layout adapts for mobile screens (single-column cards, stacked detail view) so it works on tablets as well as large kiosk displays.

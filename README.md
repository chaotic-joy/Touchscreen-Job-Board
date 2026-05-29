# 123Dentist Careers Kiosk

A single-file HTML kiosk app for displaying 123Dentist job openings at in-person events (e.g. career fairs, conferences). Visitors browse jobs by province → role category → individual listing, then scan a QR code to apply.

The app is **bilingual (French/English)**. It loads in French by default. A toggle button in the bottom bar switches to English and back.

---

## Files

| File | Purpose |
|---|---|
| `index.html` | The entire app — styles, HTML structure, job data, and JS logic |
| `Non QC JDIQ List.csv` | Source job listings for all provinces except Quebec (exported from ADP) |
| `QC JDIQ List.csv` | Source job listings for Quebec (exported from ADP, French content) |
| `index backup.html` | Pre-bilingual backup of the original English-only version |
| `123dentist_logo.png` | Logo shown in header and idle screen |
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

A breadcrumb bar at the top lets users jump back to any step. The "Recommencer / Start Over" button at the bottom always returns to the Province screen. A language toggle button on the right side of the bottom bar switches between French and English — all UI labels, province names, category names, and status labels update instantly without a page reload. Job descriptions and titles are displayed as-is from the source data.

### Job data structure

All jobs live in a single JavaScript array called `RAW_JOBS` near the top of the `<script>` block. Each entry looks like:

```js
{
  posting:     10000,
  clinic:      "Victoria Square Dental",
  title:       "Associate Dentist",
  category:    "Associate Dentist",  // raw value from CSV — see category translation below
  status:      "Commission",         // normalised code — see STATUS_LABELS below
  city:        "Regina",
  province:    "SK",
  salary:      "",                   // empty string if not listed
  description: "...",
  url:         "https://workforcenow.adp.com/..."
}
```

The app groups jobs automatically by province and category — no manual grouping needed.

### Bilingual support

All UI strings are defined in two translation objects (`FR` and `EN`) in the `<script>` block. The active language is stored in a `lang` variable (`'fr'` by default). Switching language calls `toggleLang()`, which updates the DOM and re-renders the current screen.

**Category names** are translated via `categoryName(cat)`, which looks up the raw category key in `i18n().categoryNames`. Both Non-QC English categories and QC French categories are mapped in both translation objects so they display correctly in either language.

**Province names** are translated via `provinceName(code)` (e.g. `BC` → `Colombie-Britannique` in French, `British Columbia` in English).

**Status codes** are translated via `statusLabel(s)` using the `statusLabels` map in the active translation object.

### Job description formatting

**No preprocessing needed.** Descriptions are stored as raw plain text from the CSV, exactly as exported from ADP. All formatting happens client-side at render time via the `formatDesc()` function in `index.html`.

When a job detail page opens, `formatDesc()`:

1. **Detects section headers** — scans for ~50 known patterns (English ALL-CAPS, English mixed-case, and French equivalents) and splits the text on them. Examples:

   | Type | Examples |
   |---|---|
   | English ALL-CAPS | `WHAT WE ARE OFFERING:` `SCHEDULE:` `WHAT WE ARE LOOKING FOR:` `WHO WE ARE:` `COMPENSATION:` |
   | English mixed-case | `What We Offer` `About the Role` `Who We Are` `What You'll Do` `Key Responsibilities` |
   | French ALL-CAPS | `CE QUE NOUS PROPOSONS :` `CE QUE NOUS RECHERCHONS :` `HORAIRES:` `VOS RESPONSABILITÉS :` |
   | French mixed-case | `Qui nous sommes` `À propos de nous :` `Description du poste:` `Nous offrons :` |

2. **Styles headers** as small-caps navy labels with an underline, visually separating sections.

3. **Bullet-formats list sections** — for headers like `WHAT WE ARE OFFERING:`, `WHAT WE ARE LOOKING FOR:`, `CE QUE NOUS PROPOSONS :`, `Key Responsibilities`, etc., the content is split into individual bullet items. Splitting uses capitalisation boundaries (a new item starts when a capitalised word follows content that doesn't end with a continuation word like "and", "or", "the", etc.).

4. **Passes narrative sections** (schedule, compensation, who we are, about the role) through as plain paragraphs.

5. **Drops `JOB ID:` lines** silently.

**Adding new header patterns** — if future ADP exports introduce new section headers that aren't being detected, add them to the `HEADERS` array in `formatDesc()` in `index.html`. If the new header's content should be bulleted, also add it to the `LIST_HEADERS` set. Both are near the top of the function.

### Status codes

`status` is normalised from the CSV `role_type` field to one of these codes, then translated via the active language's `statusLabels` map:

| Code | English display | French display |
|---|---|---|
| `FT` | Full-Time | Temps plein |
| `PT` | Part-Time | Temps partiel |
| `Commission` | Commission | Commission |
| `Locum` | Locum | Locum |
| `Casual` | Casual | Occasionnel |
| `Temp FT` | Temp Full-Time | Temps plein temporaire |
| `Temp PT` | Temp Part-Time | Temps partiel temporaire |
| `PT 20+` | PT (20+ hrs/wk) | TP (20+ h/sem) |

---

## Updating the job listings

Job data is loaded from two CSV files — one for Non-QC roles, one for QC — and embedded directly into `RAW_JOBS` in `index.html` using `update_jobs.py`.

### CSV formats

**Non QC JDIQ List.csv** columns:
```
role_name, role_type, posting_number, location, category, salary, description, url
```

**QC JDIQ List.csv** columns:
```
role_name, role_type, posting_number, location, postal_code, category, description, url
```

For both files:
- **role_name** must follow the format `Role Title - Clinic Name` (e.g. `Associate Dentist - Victoria Square Dental`). The script splits on the first ` - `.
- **location** must be `City, Province` (e.g. `Regina, SK`).
- **role_type** (Non-QC): `Full Time`, `Part Time`, `Commission`, `Casual`, `Locum`, `Temporary FT`, `Temporary PT`
- **role_type** (QC): `Temps plein`, `Temps partiel`, `Temps Plein Temporaire`, `Commission Part Time 20+ hours`

Replace the CSV files in the project folder with the new exports, keeping the same filenames. Description text should be left as raw plain text — do not pre-format or add HTML. The `formatDesc()` function in `index.html` handles all formatting at render time.

### 2. Run the update script

The script below reads both CSVs, normalises the data, and rewrites the `RAW_JOBS` block in `index.html`. Save it as `update_jobs.py` in the project folder and run it after replacing the CSV files.

```python
import csv, json, re

STATUS_MAP = {
    'Commission': 'Commission', 'Full Time': 'FT', 'Part Time': 'PT',
    'Casual': 'Casual', 'Locum': 'Locum',
    'Temporary FT': 'Temp FT', 'Temporary PT': 'Temp PT',
    'Temps plein': 'FT', 'Temps partiel': 'PT',
    'Temps Plein Temporaire': 'Temp FT',
    'Commission Part Time 20+ hours': 'PT 20+',
}

def parse_location(loc):
    parts = loc.rsplit(',', 1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (loc.strip(), '')

def parse_role_name(name):
    parts = name.split(' - ', 1)
    return (parts[0].strip(), parts[1].strip()) if len(parts) == 2 else (name.strip(), '')

jobs = []

for fname, has_salary in [('Non QC JDIQ List.csv', True), ('QC JDIQ List.csv', False)]:
    with open(fname, encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            title, clinic = parse_role_name(row['role_name'])
            city, province = parse_location(row['location'])
            status = STATUS_MAP.get(row['role_type'].strip(), row['role_type'].strip())
            jobs.append({
                'posting': row['posting_number'].strip(),
                'clinic': clinic, 'title': title,
                'category': row['category'].strip(),
                'status': status, 'city': city, 'province': province,
                'salary': row['salary'].strip() if has_salary else '',
                'description': row['description'].strip(),
                'url': row['url'].strip(),
            })

lines = ['const RAW_JOBS = [']
for j in jobs:
    lines.append('  ' + json.dumps(j, ensure_ascii=False) + ',')
lines[-1] = lines[-1].rstrip(',')
lines.append('];')
new_block = '\n'.join(lines)

with open('index.html', 'r', encoding='utf-8') as f:
    html = f.read()

start = html.index('const RAW_JOBS = [')
end = html.index('\n];', start) + 3
with open('index.html', 'w', encoding='utf-8') as f:
    f.write(html[:start] + new_block + html[end:])

print(f'Done. {len(jobs)} jobs written.')
```

### 3. Test it

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

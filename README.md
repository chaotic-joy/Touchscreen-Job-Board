# 123Dentist Careers Kiosk

A single-file HTML kiosk app for displaying 123Dentist job openings at in-person events (e.g. career fairs, conferences). Visitors browse jobs by province → role category → individual listing, then scan a QR code to apply.

---

## Files

| File | Purpose |
|---|---|
| `index.html` | The entire app — styles, HTML structure, job data, and JS logic |
| `Jobs May 6th.csv` | Source of truth for job listings (exported from ADP) |
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

A breadcrumb bar at the top lets users jump back to any step. The "Start Over" button at the bottom always returns to the Province screen.

### Job data structure

All jobs live in a single JavaScript array called `RAW_JOBS` near the top of the `<script>` block (currently around line 520). Each entry looks like:

```js
{
  posting: 10000,
  clinic:   "Victoria Square Dental",
  title:    "Associate Dentist",
  category: "Associate",
  status:   "Commission",       // see STATUS_LABELS below
  city:     "Regina",
  province: "SK",
  salary:   "",                 // empty string if not listed
  date:     "May 6, 2026",
  url:      "https://workforcenow.adp.com/..."
}
```

The app groups jobs automatically by province and category — no manual grouping needed.

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

### 1. Export the CSV from ADP

Export a CSV with exactly these column headers:

```
Req #, Job Title, role_type, location, category, salary, description, url
```

- **Job Title** must follow the format `Role Title - Clinic Name` (e.g. `Associate Dentist - Victoria Square Dental`). The script splits on the first ` - ` to separate title from clinic.
- **location** must be `City, Province` (e.g. `Regina, SK`).
- **role_type** must be one of: `Full Time`, `Part Time`, `Commission`, `Casual`, `Locum`, `Temporary FT`, `Temporary PT`.

Save the file in the project folder (e.g. `Jobs May 6th.csv`).

### 2. Run the Python script

Open a terminal in the project folder and run:

```python
python3 << 'EOF'
import csv

role_map = {
    'Full Time': 'FT', 'Part Time': 'PT', 'Commission': 'Commission',
    'Casual': 'Casual', 'Locum': 'Locum', 'Temporary FT': 'Temp FT', 'Temporary PT': 'Temp PT',
}

def js_str(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')

jobs = []
with open('Jobs May 6th.csv', newline='', encoding='utf-8') as f:  # ← update filename
    reader = csv.DictReader(f)
    for row in reader:
        raw_title = row['Job Title'].strip()
        title, clinic = (raw_title.split(' - ', 1) if ' - ' in raw_title else (raw_title, ''))
        title, clinic = title.strip(), clinic.strip()
        loc = row['location'].strip()
        city, province = (loc.rsplit(', ', 1) if ', ' in loc else (loc, ''))
        status = role_map.get(row['role_type'].strip(), row['role_type'].strip())
        jobs.append(f'  {{posting:{row["Req #"].strip()},clinic:"{js_str(clinic)}",title:"{js_str(title)}",category:"{js_str(row["category"].strip())}",status:"{status}",city:"{js_str(city)}",province:"{province}",salary:"{js_str(row["salary"].strip())}",date:"May 6, 2026",url:"{row["url"].strip()}"}}')  # ← update date

new_block = 'const RAW_JOBS = [\n' + ',\n'.join(jobs) + '\n];'

with open('index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find the array boundaries
start = next(i for i, l in enumerate(lines) if l.strip() == 'const RAW_JOBS = [')
end   = next(i for i in range(start, len(lines)) if lines[i].strip() == '];')

new_content = ''.join(lines[:start]) + new_block + '\n' + ''.join(lines[end+1:])

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(new_content)

print(f"Done. {len(jobs)} jobs written.")
EOF
```

Update the **filename** and **date** string at the marked lines before running.

### 3. Test it

Open `index.html` directly in a browser. No server needed. Verify:
- The province list shows the expected provinces.
- A few job detail pages load correctly and the QR code resolves to the right ADP URL.

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

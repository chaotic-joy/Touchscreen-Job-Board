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

### 1. Export the CSV from ADP

Export a CSV with exactly these column headers:

```
Req #, Job Title, role_type, location, category, salary, description, url
```

- **Job Title** must follow the format `Role Title - Clinic Name` (e.g. `Associate Dentist - Victoria Square Dental`). The script splits on the first ` - ` to separate title from clinic.
- **location** must be `City, Province` (e.g. `Regina, SK`).
- **role_type** must be one of: `Full Time`, `Part Time`, `Commission`, `Casual`, `Locum`, `Temporary FT`, `Temporary PT`.
- **description** is the full plain-text job description. The script formats it automatically.

Save the file in the project folder (e.g. `Jobs May 6th.csv`).

### 2. Save the update script

Save the following as `update_jobs.py` in the project folder. Update the `CSV_FILE` and `DATE` variables at the top before running.

```python
import csv, re, html as html_mod

CSV_FILE = 'Jobs May 6th.csv'   # ← update filename
DATE     = 'May 6, 2026'        # ← update date

# ── Section headers the formatter recognises ─────────────────────────────────
HEADERS = [
    'WE HIRE AND TRAIN THE BEST OPERATIONAL EXCELLENCE EFFORTLESS GUEST OBSESSED WHAT WE ARE OFFERING:',
    'NO WEEKENDS WHAT WE ARE LOOKING FOR:', 'GMB WHAT WE ARE OFFERING:',
    'WHAT WE ARE OFFERING:', 'WHAT WE ARE LOOKING FOR:', 'WHO WE ARE:',
    'KEY RESPONSIBILITIES:', 'QUALIFICATIONS:', 'COMPENSATION:',
    'WE OFFER:', 'WORK HOURS:', 'ABOUT US:',
    'SCHEDULE:', 'SC HEDULE:', 'SCHEDULE :', 'JOB ID:', 'JOB ID :',
    'Responsibilities and Duties:',
    'What We Are Looking For:', 'What We Are Offering:', 'What We Offer:',
    'We offer:', 'We Offer:',
    'Who We Are:', 'About Us:', 'Key Responsibilities:', 'Key Requirements:',
    'Job Overview:', 'Job Responsibilities:', 'The Opportunity:',
    'Our Ideal Candidate:', 'Looking For:', 'Minimum Qualifications:',
    'Preferred Qualifications:', 'Treatment Planning:', 'Clinical Procedures:',
    'Work Location:', 'Employment Type:', 'About the Role:',
    'What We Are Looking For', 'What We Are Offering', 'Who We Are',
    'Key Responsibilities', 'Responsibilities', 'Qualifications', 'Requirements',
    'About Us', 'Benefits', 'Schedule', 'Compensation',
    'Why You’ll Love This Opportunity', "Why You'll Love This Opportunity",
    'Why You’ll Love It',             "Why You'll Love It",
    'What You’ll Do',                 "What You'll Do",
    'What You’ll Bring',              "What You'll Bring",
    'What You Bring',
    'Why Join 123Dentist', 'About 123Dentist', 'About the Role', 'What We Offer',
]

# Headers whose content should be rendered as a bullet list
LIST_HEADERS = {
    'WHAT WE ARE OFFERING:', 'WHAT WE ARE LOOKING FOR:',
    'KEY RESPONSIBILITIES:', 'QUALIFICATIONS:', 'WE OFFER:',
    'GMB WHAT WE ARE OFFERING:', 'NO WEEKENDS WHAT WE ARE LOOKING FOR:',
    'WE HIRE AND TRAIN THE BEST OPERATIONAL EXCELLENCE EFFORTLESS GUEST OBSESSED WHAT WE ARE OFFERING:',
    'What We Are Looking For:', 'What We Are Offering:', 'What We Offer:',
    'We offer:', 'We Offer:',
    'Key Responsibilities:', 'Key Requirements:', 'Job Responsibilities:',
    'Our Ideal Candidate:', 'Looking For:',
    'Minimum Qualifications:', 'Preferred Qualifications:',
    'Treatment Planning:', 'Clinical Procedures:', 'Responsibilities and Duties:',
    'What We Are Looking For', 'What We Are Offering', 'Key Responsibilities',
    'Responsibilities', 'Qualifications', 'Requirements', 'Benefits',
    'Why You’ll Love This Opportunity', "Why You'll Love This Opportunity",
    'Why You’ll Love It',             "Why You'll Love It",
    'What You’ll Do',                 "What You'll Do",
    'What You’ll Bring',              "What You'll Bring",
    'What You Bind', 'What You Bring',
}

HEADER_RE = re.compile(
    '(' + '|'.join(re.escape(h) for h in sorted(HEADERS, key=len, reverse=True)) + ')'
)

CONTINUATION = {
    'a','an','the','of','in','on','at','for','with','to','from','by',
    'and','or','but','nor','as','per','through','about','over','under',
    'into','during','including','such','like','than','that',
    'which','who','whose','while','where','when',
    'is','are','was','were','have','has','had','be','been','being',
    'our','your','their','its','this','these','those',
    'not','no','if','so','both','either','neither',
    'each','every','some','any','all','upon',
    'across','within','between','among','toward','towards',
    'dental','oral','medical','clinical','surgical','general',
    'annual','monthly','weekly','bi-weekly',
}

def format_list_items(text):
    """Split flat text into bullet items by detecting phrase boundaries."""
    if '•' in text:   # already has bullet chars — split on them
        return None
    words = text.split()
    items, current, depth = [], [], 0
    for word in words:
        prev = current[-1].lower().rstrip('.,;:’\'"') if current else ''
        should_split = (
            current and word and word[0].isupper()
            and depth == 0
            and len(' '.join(current)) >= 12
            and prev not in CONTINUATION
            and not word.startswith('(')
        )
        if should_split:
            items.append(' '.join(current))
            current = []
        current.append(word)
        depth = max(0, depth + word.count('(') - word.count(')'))
    if current:
        items.append(' '.join(current))
    return [i.strip() for i in items if i.strip()]

def format_description(text):
    """Convert a flat ADP description string into structured HTML."""
    text = html_mod.escape(text, quote=False)
    parts = HEADER_RE.split(text)
    out = []

    intro = parts[0].strip()
    if intro:
        out.append(intro)

    for i in range(1, len(parts), 2):
        header  = parts[i]
        content = parts[i + 1].strip() if i + 1 < len(parts) else ''
        if not header.endswith(':'):
            content = re.sub(r'^:\s*', '', content)
        content = content.strip()

        display = header.rstrip(':').strip().upper()

        if header in LIST_HEADERS:
            items = format_list_items(content)
            if items is None:   # already bulleted in source
                parts_b = [p.strip() for p in content.split('•') if p.strip()]
                body = '<br>'.join('&bull; ' + p for p in parts_b) if parts_b else content
            else:
                body = '<br>'.join('&bull; ' + item for item in items)
        else:
            body = content

        # desc-sec div: CSS hides it when desc-body is empty
        out.append(
            '<div class="desc-sec"><strong>' + display +
            '</strong><div class="desc-body">' + body + '</div></div>'
        )

    return ''.join(out)

def js_str(s):
    return s.replace('\\', '\\\\').replace('"', '\\"')

ROLE_MAP = {
    'Full Time': 'FT', 'Part Time': 'PT', 'Commission': 'Commission',
    'Casual': 'Casual', 'Locum': 'Locum',
    'Temporary FT': 'Temp FT', 'Temporary PT': 'Temp PT',
}

jobs = []
with open(CSV_FILE, encoding='utf-8') as f:
    for row in csv.DictReader(f):
        raw = row['Job Title'].strip()
        title, clinic = (raw.split(' - ', 1) if ' - ' in raw else (raw, ''))
        title, clinic = title.strip(), clinic.strip()
        loc = row['location'].strip()
        city, province = (loc.rsplit(', ', 1) if ', ' in loc else (loc, ''))
        status = ROLE_MAP.get(row['role_type'].strip(), row['role_type'].strip())
        desc   = js_str(format_description(row['description'].strip()))
        jobs.append(
            '  {posting:' + row['Req #'].strip() +
            ',clinic:"'   + js_str(clinic)                    + '"' +
            ',title:"'    + js_str(title)                     + '"' +
            ',category:"' + js_str(row['category'].strip())   + '"' +
            ',status:"'   + status                            + '"' +
            ',city:"'     + js_str(city)                      + '"' +
            ',province:"' + province                          + '"' +
            ',salary:"'   + js_str(row['salary'].strip())     + '"' +
            ',date:"'     + DATE                              + '"' +
            ',description:"' + desc                          + '"' +
            ',url:"'      + row['url'].strip()                + '"}'
        )

new_block = 'const RAW_JOBS = [\n' + ',\n'.join(jobs) + '\n];'

with open('index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start = next(i for i, l in enumerate(lines) if l.strip() == 'const RAW_JOBS = [')
end   = next(i for i in range(start, len(lines)) if lines[i].strip() == '];')

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(''.join(lines[:start]) + new_block + '\n' + ''.join(lines[end + 1:]))

print('Done. ' + str(len(jobs)) + ' jobs written.')
```

### 3. Run it

```bash
python3 update_jobs.py
```

### 4. Test it

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

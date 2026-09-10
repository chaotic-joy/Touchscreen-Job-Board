import csv, re, html as html_mod

# Two source CSVs (English board + French/Quebec board) exported by the scraper.
CSV_FILES = ['EDDS - NWDE 2026.csv', 'EDDS - NWDE 2026 - QC.csv']
DATE      = 'September 10, 2026'

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

# role_type strings the two scraper boards emit → STATUS_LABELS codes in index.html
ROLE_MAP = {
    'Full Time': 'FT', 'Part Time': 'PT',
    'Temporary FT': 'Temp FT', 'Temporary PT': 'Temp PT',
    'Casual': 'Casual', 'Locum': 'Locum',
    'PT 20 hours or more per week': 'PT 20+',
    'PT less than 20 hours per week': 'PT <20',
    'Commission-based Full Time': 'Commission',
    'Commission-based Part Time': 'Commission',
    'Commission Part Time 20+ hours': 'Commission',
    # French (Quebec board)
    'Temps plein': 'FT', 'Temps partiel': 'PT',
    'Temps Plein Temporaire': 'Temp FT',
    'Temps partiel basé sur une commission': 'Commission',
    '': '',
}

jobs = []
for csv_file in CSV_FILES:
    with open(csv_file, encoding='utf-8') as f:
        for row in csv.DictReader(f):
            raw = row['role_name'].strip()          # scraper column, e.g. "Associate Dentist - Victoria Square Dental"
            title, clinic = (raw.split(' - ', 1) if ' - ' in raw else (raw, ''))
            title, clinic = title.strip(), clinic.strip()
            loc = row['location'].strip()
            city, province = (loc.rsplit(', ', 1) if ', ' in loc else (loc, ''))
            if not province and 'QC' in csv_file:   # QC board rows w/ blank location → Quebec
                province = 'QC'
            rt = row['role_type'].strip()
            status = ROLE_MAP.get(rt, rt)
            desc   = js_str(format_description(row['description'].strip()))
            jobs.append((int(row['posting_number'].strip()),
                '  {posting:' + row['posting_number'].strip() +
                ',clinic:"'   + js_str(clinic)                    + '"' +
                ',title:"'    + js_str(title)                     + '"' +
                ',category:"' + js_str(row['category'].strip())   + '"' +
                ',status:"'   + js_str(status)                    + '"' +
                ',city:"'     + js_str(city)                      + '"' +
                ',province:"' + js_str(province)                  + '"' +
                ',salary:"'   + js_str(row['salary'].strip())     + '"' +
                ',date:"'     + DATE                              + '"' +
                ',description:"' + desc                          + '"' +
                ',url:"'      + row['url'].strip()                + '"}'
            ))

jobs.sort(key=lambda t: t[0])
new_block = 'const RAW_JOBS = [\n' + ',\n'.join(entry for _, entry in jobs) + '\n];'

with open('index.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

start = next(i for i, l in enumerate(lines) if l.strip() == 'const RAW_JOBS = [')
end   = next(i for i in range(start, len(lines)) if lines[i].strip() == '];')

with open('index.html', 'w', encoding='utf-8') as f:
    f.write(''.join(lines[:start]) + new_block + '\n' + ''.join(lines[end + 1:]))

print('Done. ' + str(len(jobs)) + ' jobs written.')

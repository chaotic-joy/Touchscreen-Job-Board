#!/usr/bin/env python3
"""Refresh RAW_JOBS in index.html from the public ADP career center.

The November 2026 CSV refresh under-counted for three separate reasons:

1. Pagination. ADP ignores ``$top`` when ``$skip`` is 0 and returns 19 rows
   instead of 20. A loop that then does ``skip += 20`` skips index 19.
   Starting at ``$skip=1`` (the previous workaround) skips index 0 unless
   that requisition happens to be repeated later in the list. This script
   overlaps every page by one row, dedupes on ``itemID``, and stops only
   when the unique count equals ``meta.totalNumber``.

2. Location. The old export kept ``requisitionLocations[0]`` only. A
   posting whose New Brunswick or Nova Scotia site is a second or third
   location, or whose province is written out ("New Brunswick",
   "Nouvelle-Écosse") instead of a two-letter code, was dropped. This
   script checks every location's city, province code, subdivision name,
   street lines, and the location label.

3. Role filter. ``update_jobs.py`` itself did not filter titles, but the
   ``maritimes`` board was then cut down to hygienists and dental
   assistants. Pass ``--provinces NB,NS`` to keep every role in those
   provinces and nothing else.

The French career center is a different ``ccId`` (not just ``lang=fr_CA``
on the English center). Both are scanned. A French-only requisition is
added when its location is in the requested provinces and its posting
number is not already on the English board.
"""

from __future__ import annotations

import argparse
import html as html_mod
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from html.parser import HTMLParser

CID = "c2a72bdd-3357-40d4-ba1b-c98aada9201f"
ENGLISH_CC = "9200523617456_2"
FRENCH_CC = "9200562664414_2"
LIST_URL = (
    "https://workforcenow.adp.com/mascsr/default/careercenter/public"
    "/events/staffing/v1/job-requisitions"
)
BOARD_URL = (
    "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html"
)

# Full province names are used when a location label spells the province out
# and when a clinic suffix repeats it. Only NB and NS are kept when filtering.
PROVINCE_ALIASES = {
    "ab": "AB", "alberta": "AB",
    "bc": "BC", "british columbia": "BC", "colombie-britannique": "BC",
    "mb": "MB", "manitoba": "MB",
    "nb": "NB", "n.b.": "NB", "n.b": "NB", "new brunswick": "NB",
    "nouveau-brunswick": "NB", "nouveau brunswick": "NB",
    "nl": "NL", "newfoundland": "NL", "newfoundland and labrador": "NL",
    "terre-neuve": "NL", "terre-neuve-et-labrador": "NL",
    "ns": "NS", "n.s.": "NS", "n.s": "NS", "nova scotia": "NS",
    "nouvelle-écosse": "NS", "nouvelle-ecosse": "NS", "nouvelle écosse": "NS",
    "nt": "NT", "northwest territories": "NT",
    "nu": "NU", "nunavut": "NU",
    "on": "ON", "ontario": "ON",
    "pe": "PE", "pei": "PE", "prince edward island": "PE",
    "île-du-prince-édouard": "PE", "ile-du-prince-edouard": "PE",
    "qc": "QC", "quebec": "QC", "québec": "QC",
    "sk": "SK", "saskatchewan": "SK",
    "yt": "YT", "yukon": "YT",
}
PROVINCE_NAMES = {
    "AB": "Alberta", "BC": "British Columbia", "MB": "Manitoba",
    "NB": "New Brunswick", "NL": "Newfoundland", "NS": "Nova Scotia",
    "NT": "Northwest Territories", "NU": "Nunavut", "ON": "Ontario",
    "PE": "Prince Edward Island", "QC": "Quebec", "SK": "Saskatchewan",
    "YT": "Yukon",
}
# Postal-code first letter, used only when ADP sent no province at all.
POSTAL_PROVINCE = {"A": "NL", "B": "NS", "C": "PE", "E": "NB"}

ROLE_MAP = {
    "full time": "FT",
    "part time": "PT",
    "temporary ft": "Temp FT",
    "temporary pt": "Temp PT",
    "temporary full time": "Temp FT",
    "temporary part time": "Temp PT",
    "casual": "Casual",
    "locum": "Locum",
    "pt 20 hours or more per week": "PT 20+",
    "pt less than 20 hours per week": "PT <20",
    "commission-based full time": "Commission",
    "commission-based part time": "Commission",
    "commission part time 20+ hours": "Commission",
    "ft/pt": "FT/PT",
    "full time/part time": "FT/PT",
    "temps plein": "FT",
    "temps partiel": "PT",
    "temps plein temporaire": "Temp FT",
    "temps partiel basé sur une commission": "Commission",
}

HEADERS = [
    "WE HIRE AND TRAIN THE BEST OPERATIONAL EXCELLENCE EFFORTLESS GUEST OBSESSED WHAT WE ARE OFFERING:",
    "NO WEEKENDS WHAT WE ARE LOOKING FOR:", "GMB WHAT WE ARE OFFERING:",
    "WHAT WE ARE OFFERING:", "WHAT WE ARE LOOKING FOR:", "WHO WE ARE:",
    "KEY RESPONSIBILITIES:", "QUALIFICATIONS:", "COMPENSATION:",
    "WE OFFER:", "WORK HOURS:", "ABOUT US:",
    "SCHEDULE:", "SC HEDULE:", "SCHEDULE :", "JOB ID:", "JOB ID :",
    "Responsibilities and Duties:",
    "What We Are Looking For:", "What We Are Offering:", "What We Offer:",
    "We offer:", "We Offer:",
    "Who We Are:", "About Us:", "Key Responsibilities:", "Key Requirements:",
    "Job Overview:", "Job Responsibilities:", "The Opportunity:",
    "Our Ideal Candidate:", "Looking For:", "Minimum Qualifications:",
    "Preferred Qualifications:", "Treatment Planning:", "Clinical Procedures:",
    "Work Location:", "Employment Type:", "About the Role:",
    "What We Are Looking For", "What We Are Offering", "Who We Are",
    "Key Responsibilities", "Responsibilities", "Qualifications", "Requirements",
    "About Us", "Benefits", "Schedule", "Compensation",
    "Why You’ll Love This Opportunity", "Why You'll Love This Opportunity",
    "Why You’ll Love It", "Why You'll Love It",
    "What You’ll Do", "What You'll Do",
    "What You’ll Bring", "What You'll Bring",
    "What You Bring",
    "Why Join 123Dentist", "About 123Dentist", "About the Role", "What We Offer",
]
LIST_HEADERS = {
    "WHAT WE ARE OFFERING:", "WHAT WE ARE LOOKING FOR:",
    "KEY RESPONSIBILITIES:", "QUALIFICATIONS:", "WE OFFER:",
    "GMB WHAT WE ARE OFFERING:", "NO WEEKENDS WHAT WE ARE LOOKING FOR:",
    "WE HIRE AND TRAIN THE BEST OPERATIONAL EXCELLENCE EFFORTLESS GUEST OBSESSED WHAT WE ARE OFFERING:",
    "What We Are Looking For:", "What We Are Offering:", "What We Offer:",
    "We offer:", "We Offer:",
    "Key Responsibilities:", "Key Requirements:", "Job Responsibilities:",
    "Our Ideal Candidate:", "Looking For:",
    "Minimum Qualifications:", "Preferred Qualifications:",
    "Treatment Planning:", "Clinical Procedures:", "Responsibilities and Duties:",
    "What We Are Looking For", "What We Are Offering", "Key Responsibilities",
    "Responsibilities", "Qualifications", "Requirements", "Benefits",
    "Why You’ll Love This Opportunity", "Why You'll Love This Opportunity",
    "Why You’ll Love It", "Why You'll Love It",
    "What You’ll Do", "What You'll Do",
    "What You’ll Bring", "What You'll Bring",
    "What You Bind", "What You Bring",
}
CONTINUATION = {
    "a", "an", "the", "of", "in", "on", "at", "for", "with", "to", "from", "by",
    "and", "or", "but", "nor", "as", "per", "through", "about", "over", "under",
    "into", "during", "including", "such", "like", "than", "that",
    "which", "who", "whose", "while", "where", "when",
    "is", "are", "was", "were", "have", "has", "had", "be", "been", "being",
    "our", "your", "their", "its", "this", "these", "those",
    "not", "no", "if", "so", "both", "either", "neither",
    "each", "every", "some", "any", "all", "upon",
    "across", "within", "between", "among", "toward", "towards",
    "dental", "oral", "medical", "clinical", "surgical", "general",
    "annual", "monthly", "weekly", "bi-weekly",
}
ROLE_HINT = re.compile(
    r"hygien|hygién|assistant|dentiste|dentist|réception|reception|infirmi|"
    r"nurse|manager|coordonn|coordinator|admin|floater|inject",
    re.I,
)


def normalize_province(value):
    if not value:
        return None
    key = re.sub(r"\s+", " ", value.strip().lower().replace("’", "'"))
    return PROVINCE_ALIASES.get(key)


def province_in_text(text):
    """Find a province written in a free-text location label.

    Two-letter codes must be their own token. A substring match would treat
    Granby, QC as New Brunswick because "nb" occurs inside "granby".
    """
    if not text:
        return None
    lowered = text.lower().replace("’", "'")
    for name, code in sorted(PROVINCE_ALIASES.items(), key=lambda kv: -len(kv[0])):
        if len(name) <= 3 and "." not in name:
            continue
        if re.search(r"(?<![a-zà-ÿ])" + re.escape(name) + r"(?![a-zà-ÿ])", lowered):
            return code
    match = re.search(r"(?<![A-Za-z])(N\.?\s?B\.?|N\.?\s?S\.?)(?![A-Za-z])", text, re.I)
    if match:
        compact = re.sub(r"[^A-Za-z]", "", match.group(1)).upper()
        return {"NB": "NB", "NS": "NS"}.get(compact)
    return None


def locations_of(job):
    found = []
    for loc in job.get("requisitionLocations") or []:
        address = loc.get("address") or {}
        subdiv = address.get("countrySubdivisionLevel1") or {}
        city = (address.get("cityName") or "").strip()
        code = (subdiv.get("codeValue") or "").strip()
        long_name = (subdiv.get("longName") or subdiv.get("shortName") or "").strip()
        short = ((loc.get("nameCode") or {}).get("shortName") or "").strip()
        lines = " ".join(
            str(address.get(key) or "")
            for key in ("lineOne", "lineTwo", "lineThree", "line1", "line2", "line3")
        ).strip()
        postal = (address.get("postalCode") or "").strip()
        province = normalize_province(code) or normalize_province(long_name)
        parts = [part.strip() for part in short.split(",") if part.strip()]
        if parts and parts[-1].lower() in {"ca", "canada", "can"}:
            parts = parts[:-1]
        parsed_province = normalize_province(parts[-1]) if parts else None
        if not province:
            province = parsed_province
        if not city and parsed_province and len(parts) >= 2:
            city = parts[-2]
        if not province:
            province = province_in_text(" ".join([short, lines, long_name, city]))
        if not province and postal:
            province = POSTAL_PROVINCE.get(postal[:1].upper())
        found.append({"city": city, "province": province or "", "label": short, "postal": postal})
    return found


def matching_locations(job, provinces):
    locs = locations_of(job)
    if not provinces:
        return locs or [{"city": "", "province": "", "label": "", "postal": ""}]
    return [loc for loc in locs if loc["province"] in provinces]


def category_for(title):
    role = title.split(" - ")[0].strip().lower()
    full = title.lower()
    if "hygien" in role or "hygién" in role:
        return "Hygienist"
    if "dental assistant" in role or "chairside" in role or "assistant dentaire" in role or "assistante dentaire" in role:
        return "Dental Assistant"
    if any(k in role for k in ("dentist", "dentiste", "endodont", "periodont", "oral surgeon", "orthodont")):
        return "Associate"
    if "office manager" in role or "gestionnaire de bureau" in role:
        return "Clinic Management"
    if any(k in role for k in (
        "receptionist", "reception", "réception", "treatment coordinator", "patient coordinator",
        "patient care coordinator", "hygiene coordinator", "dental admin",
        "administrator", "admin senior", "administrative assistant", "adjoint",
    )):
        return "Reception - Clinic"
    if "floater" in role or "stéril" in role or "steril" in role:
        return "Sterilization Asst"
    if "registered nurse" in role or "infirmier" in role or "infirmière" in role:
        return "Registered Nurse"
    if "intern" in role and "marketing" in full:
        return "Marketing"
    if any(k in role for k in ("legal", "counsel")):
        return "Legal"
    if "talent acquisition" in role or "recruiter" in role:
        return "Human Resources"
    if any(k in role for k in ("paid media", "marketing", "ppc", "seo")):
        return "Marketing"
    if "infrastructure architect" in role or "it support" in role:
        return "Information Technology"
    if "accounts payable" in role or "accounts receivable" in role or "billing" in role:
        return "Accounting"
    if "manager" in role:
        return "Management"
    if "corporate development" in role:
        return "Corporate Development"
    if any(k in role for k in ("coordinator", "analyst", "facilities", "administrative")):
        return "Administrative"
    return "Other"


def strip_trailing_location(text, city, province):
    full = PROVINCE_NAMES.get(province, "")
    suffixes = []
    if city and province:
        suffixes.append(f", {city}, {province}")
        suffixes.append(f", {city} {province}")
    if city and full:
        suffixes.append(f", {city}, {full}")
        suffixes.append(f", {city} {full}")
    if province:
        suffixes.append(f", {province}")
    if full:
        suffixes.append(f", {full}")
        suffixes.append(f" {full}")
    if city and province:
        suffixes.append(f", {city}")
    for suffix in suffixes:
        if text.lower().endswith(suffix.lower()):
            return text[: -len(suffix)].strip(" ,-")
    return text


def clean_clinic(clinic, city, province):
    clinic = strip_trailing_location(clinic.strip(" -"), city, province)
    if city and clinic.lower().endswith(" in " + city.lower()):
        clinic = clinic[: -(len(city) + 4)]
    if clinic.lower() in {name.lower() for name in PROVINCE_NAMES.values()} or clinic.upper() in PROVINCE_NAMES:
        return ""
    return clinic.strip(" ,-")


def split_title(raw, city, province):
    raw = re.sub(r"\s+", " ", raw or "").strip()
    raw = strip_trailing_location(raw, city, province)
    title, clinic = raw, ""
    if re.search(r"relocate|déménager|demenager", raw, re.I):
        parts = [part.strip(" -") for part in re.split(r"\s*-\s*", raw) if part.strip(" -")]
        kept = []
        for part in parts:
            if re.fullmatch(r"relocate|déménager|demenager", part, re.I):
                continue
            if normalize_province(part):
                continue
            kept.append(part)
        if kept:
            title = kept[0]
            clinic = kept[-1] if len(kept) > 1 else ""
            return _polish_title(title), clean_clinic(clinic, city, province)
    if " - " in raw:
        title, clinic = raw.split(" - ", 1)
    else:
        # "Hygienist- Victoria Court" uses a hyphen only before the clinic.
        # Require the role side to contain no hyphen so
        # "Associate Dentist-RELOCATE- NEW BRUNSWICK- ..." is not cut in half.
        hyphen_space = re.match(r"^([^-]+?)- (.+)$", raw)
        if hyphen_space and ROLE_HINT.search(hyphen_space.group(1)):
            title, clinic = hyphen_space.group(1), hyphen_space.group(2)
        elif raw.count("-") == 1:
            left, right = raw.split("-", 1)
            if ROLE_HINT.search(left) and right[:1].isalpha():
                title, clinic = left, right
    if not clinic and "," in title:
        left, right = [part.strip() for part in title.rsplit(",", 1)]
        if right and len(right) <= 40 and "." not in right and right.lower() != (city or "").lower():
            title, clinic = left, right
    return _polish_title(title), clean_clinic(clinic, city, province)


def _polish_title(title):
    return re.sub(r"^(?:full[\s-]?time|part[\s-]?time|temporary)\s+", "", title.strip(" -"), flags=re.I).strip()


def clinic_from_description(text):
    """ADP's usual opening line names the practice: 'The team at X located in City'."""
    match = re.search(r"The team at ([^.]{2,80}?) (?:located )?in\b", text or "", re.I)
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip(" ,-")


def refine_clinic(title, clinic, description, city, province):
    found = clean_clinic(clinic_from_description(description), city, province)
    if not found:
        return title, clinic
    if not clinic or (found.lower().startswith(clinic.lower()) and len(found) > len(clinic)):
        return title, found
    return title, clinic


def format_salary(pay):
    if not pay:
        return ""
    minimum = (pay.get("minimumRate") or {}).get("amountValue")
    maximum = (pay.get("maximumRate") or {}).get("amountValue")
    currency = ((pay.get("minimumRate") or pay.get("maximumRate") or {}).get("currencyCode") or "CAD")

    def positive(number):
        return isinstance(number, (int, float)) and number > 0

    if not positive(minimum) and not positive(maximum):
        return ""
    top = max(number for number in (minimum, maximum) if positive(number))
    unit = "Annually" if top >= 1000 else "Hourly"

    def fmt(number):
        if unit == "Annually":
            return f"{number:.2f}"
        if float(number).is_integer():
            return str(int(number))
        return f"{number:.2f}"

    if positive(minimum) and positive(maximum) and minimum != maximum:
        return f"{fmt(minimum)} To {fmt(maximum)} ({currency}) {unit}"
    if positive(maximum) and not positive(minimum):
        return f"Up to {fmt(maximum)} ({currency}) {unit}"
    amount = minimum if positive(minimum) else maximum
    return f"{fmt(amount)} ({currency}) {unit}"


def infer_status(title, description, work_level):
    mapped = ROLE_MAP.get((work_level or "").strip().lower())
    if mapped is not None:
        return mapped
    if work_level and work_level.strip():
        return work_level.strip()
    blob = f"{title} {description}".lower()
    if "locum" in title.lower():
        return "Locum"
    has_part = "part-time" in blob or "part time" in blob or "temps partiel" in blob
    has_full = "full-time" in blob or "full time" in blob or "temps plein" in blob
    if has_full and has_part:
        return "FT/PT"
    if has_part:
        return "PT"
    if has_full:
        return "FT"
    if "casual" in blob:
        return "Casual"
    return ""


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {"p", "div", "h1", "h2", "h3", "h4", "br", "tr", "li", "ul", "ol"}:
            self.parts.append("\n")
        if tag == "li":
            self.parts.append("• ")

    def handle_endtag(self, tag):
        if tag in {"p", "div", "h1", "h2", "h3", "h4", "li", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        self.parts.append(data)


def html_to_text(value):
    if not value:
        return ""
    parser = _TextExtractor()
    parser.feed(value)
    parser.close()
    lines = []
    for line in "".join(parser.parts).splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if line:
            lines.append(line)
    return " ".join(lines)


def format_list_items(text):
    if "•" in text:
        return None
    words = text.split()
    items, current, depth = [], [], 0
    for word in words:
        prev = current[-1].lower().rstrip(".,;:’'\"") if current else ""
        should_split = (
            current and word and word[0].isupper()
            and depth == 0
            and len(" ".join(current)) >= 12
            and prev not in CONTINUATION
            and not word.startswith("(")
        )
        if should_split:
            items.append(" ".join(current))
            current = []
        current.append(word)
        depth = max(0, depth + word.count("(") - word.count(")"))
    if current:
        items.append(" ".join(current))
    return [item.strip() for item in items if item.strip()]


CANONICAL_HEADERS = {}
for _header in HEADERS:
    CANONICAL_HEADERS.setdefault(_header.casefold(), _header)
HEADER_RE = re.compile(
    "(" + "|".join(re.escape(h) for h in sorted(HEADERS, key=len, reverse=True)) + ")",
    re.IGNORECASE,
)


def format_description(text):
    text = html_mod.escape(text or "", quote=False)
    parts = HEADER_RE.split(text)
    out = []
    intro = parts[0].strip()
    if intro:
        out.append(intro)
    for index in range(1, len(parts), 2):
        header = CANONICAL_HEADERS.get(parts[index].casefold(), parts[index])
        content = parts[index + 1].strip() if index + 1 < len(parts) else ""
        if not header.endswith(":"):
            content = re.sub(r"^:\s*", "", content)
        content = content.strip()
        display = header.rstrip(":").strip().upper()
        if header in LIST_HEADERS:
            items = format_list_items(content)
            if items is None:
                bullets = [part.strip() for part in content.split("•") if part.strip()]
                body = "<br>".join("&bull; " + part for part in bullets) if bullets else content
            else:
                body = "<br>".join("&bull; " + item for item in items)
        else:
            body = content
        out.append(
            '<div class="desc-sec"><strong>' + display
            + '</strong><div class="desc-body">' + body + "</div></div>"
        )
    return "".join(out)


def js_str(value):
    return (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\r", " ")
        .replace("\n", " ")
    )


def fetch_json(url, lang, attempts=4):
    request = urllib.request.Request(url, headers={
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": lang.replace("_", "-"),
        "locale": lang,
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0",
    })
    last_error = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.loads(response.read().decode())
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            time.sleep(1.2 * (attempt + 1))
    raise RuntimeError(f"ADP request failed for {url}: {last_error}")


def list_url(cc_id, lang, skip, top):
    stamp = str(int(time.time() * 1000))
    return (
        f"{LIST_URL}?cid={CID}&ccId={cc_id}&lang={lang}&locale={lang}"
        f"&$top={top}&$skip={skip}&timeStamp={stamp}"
    )


def fetch_board(cc_id, lang, top=20):
    """Page a career center until every requisition in meta.totalNumber is held."""
    seen = {}
    skip = 0
    total = None
    stalls = 0
    pages = 0
    while True:
        payload = fetch_json(list_url(cc_id, lang, skip, top), lang)
        meta = payload.get("meta") or {}
        total = meta.get("totalNumber") or 0
        jobs = payload.get("jobRequisitions") or []
        start = meta.get("startSequence")
        if not isinstance(start, int):
            start = skip
        pages += 1
        if not jobs:
            break
        new = 0
        for job in jobs:
            item_id = job.get("itemID")
            if item_id and item_id not in seen:
                seen[item_id] = job
                new += 1
        print(
            f"  {lang} {cc_id} skip={skip} start={start} "
            f"rows={len(jobs)} new={new} unique={len(seen)}/{total}",
            file=sys.stderr,
        )
        if total and len(seen) >= total:
            break
        # Overlap the next window by one row. $skip=0 returns 19 rows even
        # when $top is 20, so advancing by a fixed 20 drops a requisition.
        nxt = start + max(1, len(jobs) - 1)
        if nxt <= skip:
            nxt = skip + 1
        skip = nxt
        if new == 0:
            stalls += 1
            if stalls > 4:
                break
        else:
            stalls = 0
        if skip > (total or 0) + top:
            break
        time.sleep(0.12)
    if total and len(seen) != total:
        raise RuntimeError(
            f"{lang} {cc_id} returned {len(seen)} unique requisitions, "
            f"but meta.totalNumber is {total}. Refusing to write a short list."
        )
    print(f"  fetched {len(seen)} {lang} requisitions in {pages} pages", file=sys.stderr)
    return list(seen.values())


def fetch_detail(cc_id, lang, item_id):
    url = (
        f"{LIST_URL}/{item_id}?cid={CID}&ccId={cc_id}&lang={lang}&locale={lang}"
        f"&timeStamp={int(time.time() * 1000)}"
    )
    payload = fetch_json(url, lang)
    if isinstance(payload, dict) and payload.get("jobRequisitions"):
        return payload["jobRequisitions"][0]
    return payload


def apply_url(cc_id, lang, item_id):
    return (
        f"{BOARD_URL}?cid={CID}&ccId={cc_id}&type=JS&lang={lang}"
        f"&jobId={item_id}&source=CC3"
    )


def group_rows(job, provinces):
    """One kiosk row per province so a multi-province posting is visible in each."""
    chosen = matching_locations(job, provinces)
    if not chosen:
        return []
    grouped = {}
    for loc in chosen:
        province = loc["province"]
        bucket = grouped.setdefault(province, [])
        if loc["city"] and loc["city"] not in bucket:
            bucket.append(loc["city"])
    rows = []
    for province, cities in grouped.items():
        rows.append({"province": province, "city": " / ".join(cities)})
    return rows


def build_record(job, detail, place, cc_id, lang, stamped):
    raw_title = (job.get("requisitionTitle") or detail.get("requisitionTitle") or "").strip()
    description_text = html_to_text(detail.get("requisitionDescription") or "")
    title, clinic = split_title(raw_title, place["city"].split(" / ")[0], place["province"])
    title, clinic = refine_clinic(title, clinic, description_text, place["city"].split(" / ")[0], place["province"])
    work = ((job.get("workLevelCode") or detail.get("workLevelCode") or {}).get("shortName") or "")
    status = infer_status(raw_title, description_text, work)
    posting = str(job.get("clientRequisitionID") or "").strip()
    return {
        "posting": int(posting),
        "clinic": clinic,
        "title": title,
        "category": category_for(raw_title),
        "status": status,
        "city": place["city"],
        "province": place["province"],
        "salary": format_salary(job.get("payGradeRange") or detail.get("payGradeRange")),
        "date": stamped,
        "description": format_description(description_text),
        "url": apply_url(cc_id, lang, job.get("itemID")),
    }


def record_to_js(record):
    return (
        "  {posting:" + str(record["posting"])
        + ',clinic:"' + js_str(record["clinic"]) + '"'
        + ',title:"' + js_str(record["title"]) + '"'
        + ',category:"' + js_str(record["category"]) + '"'
        + ',status:"' + js_str(record["status"]) + '"'
        + ',city:"' + js_str(record["city"]) + '"'
        + ',province:"' + js_str(record["province"]) + '"'
        + ',salary:"' + js_str(record["salary"]) + '"'
        + ',date:"' + js_str(record["date"]) + '"'
        + ',description:"' + js_str(record["description"]) + '"'
        + ',url:"' + record["url"] + '"}'
    )


def write_index(records, path):
    with open(path, encoding="utf-8") as handle:
        lines = handle.readlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == "const RAW_JOBS = [")
    end = next(i for i in range(start, len(lines)) if lines[i].strip() == "];")
    block = "const RAW_JOBS = [\n" + ",\n".join(record_to_js(record) for record in records) + "\n];\n"
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("".join(lines[:start]) + block + "".join(lines[end + 1:]))


def collect(provinces):
    sources = [
        (ENGLISH_CC, "en_CA"),
        (ENGLISH_CC, "fr_CA"),
        (FRENCH_CC, "fr_CA"),
    ]
    chosen = {}
    for cc_id, lang in sources:
        for job in fetch_board(cc_id, lang):
            posting = str(job.get("clientRequisitionID") or "").strip()
            if not posting.isdigit():
                continue
            places = group_rows(job, provinces)
            if not places:
                continue
            for place in places:
                key = (posting, place["province"])
                # English text wins when the same posting is also on the French board.
                if key in chosen and chosen[key]["lang"] == "en_CA":
                    continue
                chosen[key] = {"job": job, "place": place, "cc_id": cc_id, "lang": lang}
    return chosen


def refresh(provinces, index_path, stamped, dry_run):
    chosen = collect(provinces)
    records = []
    ordered = sorted(chosen.items(), key=lambda item: (int(item[0][0]), item[0][1]))
    for (posting, _province), item in ordered:
        job = item["job"]
        print(f"  detail {posting} {job.get('requisitionTitle')}", file=sys.stderr)
        detail = fetch_detail(item["cc_id"], item["lang"], job["itemID"])
        records.append(build_record(job, detail, item["place"], item["cc_id"], item["lang"], stamped))
        time.sleep(0.08)
    records.sort(key=lambda record: (record["posting"], record["province"], record["city"]))
    keys = [(record["posting"], record["province"], record["city"]) for record in records]
    if len(keys) != len(set(keys)):
        raise RuntimeError("duplicate posting/province/city rows")
    if provinces and any(record["province"] not in provinces for record in records):
        raise RuntimeError("a row escaped the province filter")
    if not dry_run:
        if not records:
            raise RuntimeError("refusing to wipe RAW_JOBS with an empty result")
        write_index(records, index_path)
    return records


def self_test():
    granby = {
        "requisitionLocations": [{
            "address": {"cityName": "Granby", "countrySubdivisionLevel1": {"codeValue": "QC"}, "postalCode": "J2G 1A1"},
            "nameCode": {"shortName": "Granby, QC, CA"},
        }],
        "requisitionTitle": "Dentiste - Lapointe Granby",
        "clientRequisitionID": "1",
    }
    assert matching_locations(granby, {"NB", "NS"}) == []
    assert province_in_text("Granby, QC, CA") is None
    assert province_in_text("Dieppe, NB, CA") == "NB"
    assert province_in_text("Nouvelle-Écosse") == "NS"
    multi = {
        "requisitionLocations": [
            {"address": {"cityName": "Toronto", "countrySubdivisionLevel1": {"codeValue": "ON"}}, "nameCode": {"shortName": "Toronto, ON, CA"}},
            {"address": {"cityName": "Fredericton", "countrySubdivisionLevel1": {"longName": "New Brunswick"}, "postalCode": "E3B 1A1"}, "nameCode": {"shortName": "York Dental, Fredericton"}},
        ]
    }
    matched = matching_locations(multi, {"NB", "NS"})
    assert len(matched) == 1 and matched[0]["province"] == "NB" and matched[0]["city"] == "Fredericton"
    title, clinic = split_title("Certified Dental Assistant - Luxe Dental Group, Saint John, NB", "Saint John", "NB")
    assert (title, clinic) == ("Certified Dental Assistant", "Luxe Dental Group"), (title, clinic)
    title, clinic = split_title("Hygienist- Victoria Court", "Truro", "NS")
    assert (title, clinic) == ("Hygienist", "Victoria Court"), (title, clinic)
    title, clinic = split_title("Certified Dental Assistant, Truro NS", "Truro", "NS")
    assert (title, clinic) == ("Certified Dental Assistant", ""), (title, clinic)
    title, clinic = split_title(
        "Associate Dentist-RELOCATE- NEW BRUNSWICK- Dental Health Centre", "Dieppe", "NB"
    )
    assert (title, clinic) == ("Associate Dentist", "Dental Health Centre"), (title, clinic)
    title, clinic = split_title("Full Time Hygienist, Herring Cove Nova Scotia", "Halifax", "NS")
    assert (title, clinic) == ("Hygienist", "Herring Cove"), (title, clinic)
    assert category_for("Dental Receptionist - Herring Cove") == "Reception - Clinic"
    assert category_for("Registered Nurse, Victoria Court") == "Registered Nurse"
    assert format_salary({"minimumRate": {"amountValue": 45, "currencyCode": "CAD"}, "maximumRate": {"amountValue": 50, "currencyCode": "CAD"}}) == "45 To 50 (CAD) Hourly"
    print("self-test ok")


def parse_provinces(value):
    if not value:
        return set()
    codes = set()
    for part in value.split(","):
        code = normalize_province(part) or part.strip().upper()
        if code not in PROVINCE_NAMES:
            raise SystemExit(f"unknown province {part!r}")
        codes.add(code)
    return codes


def main(argv):
    parser = argparse.ArgumentParser(description="Rewrite index.html RAW_JOBS from the ADP career center.")
    parser.add_argument("--provinces", default="", help="Comma-separated province codes to keep, e.g. NB,NS. Omit to keep every province.")
    parser.add_argument("--index", default="index.html")
    parser.add_argument("--date", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args(argv)
    if args.self_test:
        self_test()
        return 0
    provinces = parse_provinces(args.provinces)
    stamped = args.date or date.today().strftime("%B %-d, %Y")
    records = refresh(provinces, args.index, stamped, args.dry_run)
    label = ",".join(sorted(provinces)) if provinces else "ALL"
    print(f"{len(records)} jobs ({label})")
    for record in records:
        clinic = record["clinic"] or "-"
        print(f"{record['posting']}\t{record['province']}\t{record['city']}\t{record['category']}\t{record['status']}\t{record['title']}\t{clinic}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

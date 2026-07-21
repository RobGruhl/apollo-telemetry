#!/usr/bin/env python3
"""Regenerate the DATA block in index.html from Cloudflare analytics.

Runs hourly via GitHub Actions (.github/workflows/refresh.yml). Reads the
read-only analytics token from CLOUDFLARE_READ_TOKEN. Stdlib only.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

TOKEN = os.environ["CLOUDFLARE_READ_TOKEN"]
ZONE_APOLLO = "878135f576ba082913c9b40ad05e500d"      # apollo13.quest
ZONE_SKELETON = "e96996f293c70590b9a5e509277e61ed"    # walkingskeleton.org
TELEMETRY_START = "2026-07-21"

# Only successful page requests from real-looking browsers count as "verified".
HUMAN_FILTER = (
    'edgeResponseStatus: 200, clientRequestPath_notlike: "%.env%", '
    'AND: [{userAgent_notlike: "%Headless%"}, {userAgent_notlike: "%Go-http-client%"}, '
    '{userAgent_notlike: "%curl%"}, {userAgent_notlike: "%bot%"}, {userAgent_notlike: "%python%"}, '
    '{userAgent_notlike: "%spider%"}, {userAgent_notlike: "%crawl%"}]'
)

SCOUT_FILTER = HUMAN_FILTER + ', clientDeviceType: "mobile", clientCountryName: "US"'

DECISION_NUMBERS = {  # slide number -> decision number (CLAUDE.md slide inventory)
    "04": 1, "05": 2, "06": 3, "09": 4, "11": 5,
    "12": 6, "13": 7, "16": 8, "17": 9, "18": 10,
}

COUNTRY_NAMES = {
    "US": "United States", "GB": "United Kingdom", "DE": "Germany", "FR": "France",
    "CA": "Canada", "AU": "Australia", "IE": "Ireland", "UA": "Ukraine", "PL": "Poland",
    "SG": "Singapore", "JP": "Japan", "IN": "India", "BR": "Brazil", "MX": "Mexico",
    "NL": "Netherlands", "SE": "Sweden", "NO": "Norway", "ES": "Spain", "IT": "Italy",
    "MY": "Malaysia", "TR": "Turkey", "CN": "China", "KR": "South Korea", "NZ": "New Zealand",
}


def gql(query, tries=4):
    req = urllib.request.Request(
        "https://api.cloudflare.com/client/v4/graphql",
        data=json.dumps({"query": query}).encode(),
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
    )
    out = None
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                out = json.load(resp)
            break
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < tries - 1:
                time.sleep(20 * (attempt + 1))
                continue
            raise
    assert out is not None
    if out.get("errors"):
        raise RuntimeError(f"GraphQL error: {out['errors']}")
    return out["data"]["viewer"]["zones"][0]


def adaptive(zone, filters, dims, limit=30, order=None):
    dim_part = f"dimensions {{ {dims} }} " if dims else ""
    order_part = f", orderBy: [{order}]" if order else ""
    q = (f'{{ viewer {{ zones(filter: {{zoneTag: "{zone}"}}) {{ '
         f'httpRequestsAdaptiveGroups(limit: {limit}, filter: {{{filters}}}{order_part}) '
         f'{{ {dim_part}sum {{ visits }} count }} }} }} }}')
    return gql(q)["httpRequestsAdaptiveGroups"]


def flag(code):
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code.upper()) if len(code) == 2 else "🏳️"


def friendly_page(path):
    if path == "/":
        return "Landing page", "/"
    stem = path.rsplit("/", 1)[-1].removesuffix(".html")
    if path == "/timeline.html":
        return "Timeline", "/timeline"
    if path == "/privacy.html":
        return "Privacy explainer", "/privacy"
    if path.startswith("/explore/"):
        return "Explore: " + stem.replace("-", " ").capitalize(), f"/explore/{stem}"
    m = re.match(r"(\d\d)-(.+)", stem)
    if m:
        num, rest = m.group(1), m.group(2).replace("-", " ")
        if num == "30":
            return "Mission complete 🏆", "/slides/30"
        name = rest[0].upper() + rest[1:]
        if num in DECISION_NUMBERS:
            name = f"Decision {DECISION_NUMBERS[num]} · {name}"
        return name, f"/slides/{num}"
    return stem, path


def main():
    now = datetime.now(timezone.utc)
    today = now.date()
    midnight = f"{today}T00:00:00Z"

    # Free-plan adaptive queries are capped at a 1-day range, so fetch each day separately.
    days, by_day = [], {}
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        if str(d) < TELEMETRY_START:
            days.append({"d": d.strftime("%b %-d"), "v": None})
            continue
        rows = adaptive(ZONE_APOLLO,
                        f'datetime_geq: "{d}T00:00:00Z", datetime_lt: "{d + timedelta(days=1)}T00:00:00Z", '
                        f'{SCOUT_FILTER}', "date")
        v = sum(g["sum"]["visits"] for g in rows)
        by_day[str(d)] = v
        days.append({"d": d.strftime("%b %-d"), "v": v})

    countries = [
        {"flag": flag(g["dimensions"]["clientCountryName"]),
         "name": COUNTRY_NAMES.get(g["dimensions"]["clientCountryName"], g["dimensions"]["clientCountryName"]),
         "v": g["sum"]["visits"]}
        for g in adaptive(ZONE_APOLLO, f'datetime_geq: "{midnight}", {HUMAN_FILTER}',
                          "clientCountryName", order="sum_visits_DESC")
        if g["sum"]["visits"] > 0
    ]

    raw_pages = adaptive(ZONE_APOLLO, f'datetime_geq: "{midnight}", {SCOUT_FILTER}',
                         "clientRequestPath", order="count_DESC")
    all_verified = sum(g["sum"]["visits"] for g in adaptive(
        ZONE_APOLLO, f'datetime_geq: "{midnight}", {HUMAN_FILTER}', "clientDeviceType"))
    page_rows, completion_row, completions = [], None, 0
    for g in raw_pages:
        p = g["dimensions"]["clientRequestPath"]
        if not (p == "/" or p.endswith(".html")):
            continue
        name, label = friendly_page(p)
        row = {"name": name, "path": label, "v": g["count"]}
        if label == "/slides/30":
            completion_row, completions = row, g["count"]
        else:
            page_rows.append(row)
    pages = page_rows[:11 if completion_row else 12]
    if completion_row:
        pages.append(completion_row)

    rollup = gql(f'{{ viewer {{ zones(filter: {{zoneTag: "{ZONE_APOLLO}"}}) {{ '
                 f'httpRequests1dGroups(limit: 5, filter: {{date: "{today}"}}) '
                 f'{{ uniq {{ uniques }} }} }} }} }}')["httpRequests1dGroups"]
    uniques = rollup[0]["uniq"]["uniques"] if rollup else 0

    all_reqs = sum(g["count"] for g in adaptive(
        ZONE_APOLLO, f'datetime_geq: "{midnight}"', "clientCountryName", limit=50))
    filtered_out = max(0, all_reqs - sum(
        g["count"] for g in adaptive(ZONE_APOLLO, f'datetime_geq: "{midnight}", {HUMAN_FILTER}',
                                     "clientCountryName", limit=50)))
    noise = (f"Filtered out today: {filtered_out} requests from scanners, crawlers, and other "
             f"automated clients (secrets probes all get 404s — the site is static and hosts no "
             f"secrets). Only real-browser sessions count above.") if filtered_out else \
        "No bot traffic filtered today."

    ws = adaptive(ZONE_SKELETON, f'datetime_geq: "{midnight}", {HUMAN_FILTER}', "", limit=5)
    ws_visits = sum(g["sum"]["visits"] for g in ws)

    visits_today = by_day.get(str(today), 0) or 0
    y_max = next(m for m in (20, 50, 100, 200, 500, 1000)
                 if m > max((d["v"] or 0) for d in days))
    ct = now - timedelta(hours=5)  # Central Daylight Time

    data = {
        "snapshotLocal": ct.strftime("%b %-d · %H:%M CT"),
        "snapshotUTC": now.strftime("%Y-%m-%dT%H:%MZ"),
        "yMax": y_max,
        "tiles": {"visits": visits_today, "allVerified": all_verified, "uniques": uniques,
                  "completions": completions},
        "wsVisits": ws_visits,
        "noiseNote": noise,
        "days": days,
        "pages": pages,
        "countries": countries,
    }

    path = os.path.join(os.path.dirname(__file__), "..", "index.html")
    src = open(path).read()
    block = ("  // ===== DATA:BEGIN ===== (regenerated by scripts/refresh.py — do not hand-edit "
             "between markers)\n  const DATA = " + json.dumps(data, ensure_ascii=False, indent=2)
             + ";\n  // ===== DATA:END =====")
    out = re.sub(r"  // ===== DATA:BEGIN =====.*?// ===== DATA:END =====", block, src, flags=re.S)
    if out == src:
        print("no change")
        return
    open(path, "w").write(out)
    print(f"refreshed: {visits_today} mobile visits ({all_verified} all-device), {len(countries)} countries, "
          f"{completions} completions, ws {ws_visits}")


if __name__ == "__main__":
    main()

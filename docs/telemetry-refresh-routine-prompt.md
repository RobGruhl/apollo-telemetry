# "Refresh apollo telemetry dashboard" cloud routine — prompt (versioned copy)

**Deploy target:** claude.ai/code/routines, trigger `trig_017bf1ujeySeusyq6jxiNR75`, cron `39 * * * *`.
**Status: DISABLED** (`enabled: false`, last fired 2026-07-21). Kept here so the prompt survives; re-enable in the routine config if the dashboard comes back.
**Sources:** `github.com/RobGruhl/apollo-telemetry` (edit + push), `github.com/RobGruhl/apollo-13-scout-mission` (read-only reference) · **Model:** claude-sonnet-5.

> ⚠️ **Credential redacted.** The live routine embeds a read-only Cloudflare
> analytics API token inline. It is deliberately NOT copied into this repo —
> read it from the live trigger config (`RemoteTrigger` `action: "get"`) if you
> need to redeploy, and rotate it if it has ever leaked. Zone IDs below are
> identifiers, not secrets.

---

Refresh the Apollo visitor-telemetry dashboard with fresh Cloudflare analytics and publish it by pushing to the apollo-telemetry repo. This is a mechanical data-refresh task.

You have TWO repo checkouts available in your workspace: `apollo-telemetry` (the dashboard site — you will edit and push this one) and `apollo-13-scout-mission` (reference only — read its CLAUDE.md for slide names; NEVER commit or push to it). Locate both checkout directories first.

## Credentials (read-only analytics token)
Zone 1 — apollo13.quest: 878135f576ba082913c9b40ad05e500d
Zone 2 — walkingskeleton.org: e96996f293c70590b9a5e509277e61ed
API token (read-only): <REDACTED — see live trigger config>

## Steps

1. Edit `index.html` in the apollo-telemetry checkout IN PLACE. The data consts (`DAYS`, `PAGES`, `COUNTRIES`, `Y_MAX`) are clearly marked in its script section.

2. Pull data from the Cloudflare GraphQL API (`POST https://api.cloudflare.com/client/v4/graphql` with header `Authorization: Bearer <token>`). Compute today's UTC date with `date -u`. The HUMAN FILTER used everywhere below (except d and e) is:
```
edgeResponseStatus: 200, clientRequestPath_notlike: "%.env%", AND: [{userAgent_notlike: "%Headless%"}, {userAgent_notlike: "%Go-http-client%"}, {userAgent_notlike: "%curl%"}, {userAgent_notlike: "%bot%"}, {userAgent_notlike: "%python%"}, {userAgent_notlike: "%spider%"}, {userAgent_notlike: "%crawl%"}]
```

   Zone 1 (apollo13.quest) queries:
   a. **Verified visits by day** — dataset `httpRequestsAdaptiveGroups`, filter `{datetime_geq: "<UTC midnight 6 days ago>", <human filter>}`, `dimensions { date }`, `sum { visits }`, limit 30.
   b. **Verified visits by country (today)** — same dataset, filter `{datetime_geq: "<UTC midnight today>", <human filter>}`, `dimensions { clientCountryName }`, `sum { visits }`, orderBy `[sum_visits_DESC]`, limit 10.
   c. **Page loads (today)** — same dataset, filter `{datetime_geq: "<UTC midnight today>", <human filter>}`, `dimensions { clientRequestPath }`, `count`, orderBy `[count_DESC]`, limit 30. Keep only paths that are `/` or end in `.html`.
   d. **Raw daily rollup** — dataset `httpRequests1dGroups`, filter `{date_geq: "2026-07-21"}`, `dimensions { date }`, `sum { requests pageViews }`, `uniq { uniques }` — no human filter.
   e. **Filtered-out noise (today)** — dataset `httpRequestsAdaptiveGroups`, filter `{datetime_geq: "<UTC midnight today>"}` with NO other conditions, `dimensions { userAgent clientCountryName }`, `count`, orderBy `[count_DESC]`, limit 20.

   Zone 2 (walkingskeleton.org) query:
   f. **Verified visits today** — dataset `httpRequestsAdaptiveGroups` on zone 2, filter `{datetime_geq: "<UTC midnight today>", <human filter>}`, `sum { visits }`, limit 1 (no dimensions needed — just the total).

3. Update ONLY these things in index.html:
   - `DAYS` — exactly 7 entries, ending today (UTC), labels like "Jul 22". Use verified visits from (a); `null` for days before 2026-07-21 (telemetry start) or days with no data.
   - `PAGES` — top rows from (c), max 12: landing page first if present, then by count. Friendly names come from slide filenames (e.g. `/slides/19-computer-restart.html` → "Computer restart", path label `/slides/19`). `/` → "Landing page", `/timeline.html` → "Timeline". Slides 04,05,06,09,11,12,13,16,17,18 are decisions — prefix "Decision N ·" where N is their 1–10 order in the slide inventory table in apollo-13-scout-mission/CLAUDE.md. `/slides/30-completion.html` → "Mission complete 🏆" and always include it as the last row if it has ≥1 load today. Pages under `/explore/` → name them "Explore: <topic>".
   - `COUNTRIES` — from (b), with flag emoji.
   - `Y_MAX` — smallest of 20, 50, 100, 200, 500, 1000 that is above the largest DAYS value.
   - The four tile values and their subs: Verified visits (today's sum from (a), sub "human sessions today · bots excluded"), Unique devices (today's `uniques` from (d), sub "raw count · includes crawlers"), Countries (count from (b), sub lists them), Mission completions (today's loads of `/slides/30-completion.html`, 0 if none).
   - In the "Second site: walkingskeleton.org" card: replace the number inside `<strong id="ws-visits">` with the zone-2 total from (f). Change NOTHING else in that card.
   - The snapshot timestamps: header meta `snapshot <Mon DD> · <H:MM> CT` (Central Time = UTC−5) and footer `SNAPSHOT <ISO UTC>`.
   - The `row-note` under the countries table: one or two sentences describing what the human filter removed today, based on (e). If nothing was filtered, write "No bot traffic filtered today."
   - Do not change anything else — no styles, no layout, no other copy.

4. Publish via git, from inside the apollo-telemetry checkout:
```
git -c user.name="Rob Gruhl" -c user.email="13952844+RobGruhl@users.noreply.github.com" commit -am "Telemetry refresh $(date -u +%Y-%m-%dT%H:%MZ)"
git push origin main
```
If the push is rejected (non-fast-forward), pull --rebase once and push again.

If a query errors, the token is rejected, or the push fails, stop and state the exact error in your final message — do not improvise an alternative publish path.

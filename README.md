# Apollo Mission Telemetry

Auto-refreshing visitor dashboard for [apollo13.quest](https://apollo13.quest/) (and its
companion site [walkingskeleton.org](https://walkingskeleton.org/)).

**View it**: https://robgruhl.github.io/apollo-telemetry/

An hourly scheduled Claude Code cloud agent pulls aggregate, bot-filtered visitor counts
from Cloudflare's analytics API, bakes them into `index.html`, and pushes the update here —
GitHub Pages serves the result. The commit history is the measurement log.

Aggregate counts only (visits, pages, countries). No cookies, no personal data — see
[apollo13.quest/privacy.html](https://apollo13.quest/privacy.html) for the whole philosophy.

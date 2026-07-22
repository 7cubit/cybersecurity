# QA / judgment-call log

## 2026-07-22 — Self-audit of the tool, fixes deferred pending owner go-ahead

**Request:** "audit it and any suggestion on the security enhancement of any software."

**Done:** Full blue-team self-audit of `scripts/orchestrate.py` + `scripts/roster.yaml`,
written to `SECURITY_AUDIT.md`, plus an independent background cross-check. Verified
factual claims (pathlib `.env` suffix behaviour; macOS `ARG_MAX` = 1,048,576).

**Findings (reconciled with the independent cross-check):** **2 HIGH** (1: sensitive
files — config/credentials/logs/source-with-secrets — shipped to providers unredacted;
2: prompt injection coercing a false "all-clear" — upgraded from MEDIUM), **4 MEDIUM**
(whole-run crash on malformed worker output via unguarded `merge()`, reproduced;
`shell=True` supply-chain; silent ensemble degradation / ARG_MAX; `read_target` reviews
the wrong thing incl. the broken piped-diff workflow, reproduced), **3 LOW** (report
world-readable 0644 + error leakage; token-strip corrupts content; symlink escape) +
info. All mechanical bugs empirically reproduced. The cross-check upgraded the picture
from 1 HIGH to 2 HIGH + a crash bug; full detail + 7-item roadmap in `SECURITY_AUDIT.md`.

**Judgment call — why fixes were NOT auto-applied:** the request was "audit + suggest,"
not "fix." Several fixes are design decisions with trade-offs (e.g. removing
`shell=True`; how aggressive redaction should be; whether to skip `.log` by default),
so they were written up and left for owner approval rather than changed silently.
The HIGH (secret redaction/denylist) is strongly recommended before any real-world
use and can be implemented immediately on request.

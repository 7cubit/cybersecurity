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

## 2026-07-24 — All deferred audit findings fixed, docs brought in line

**Request:** "Fix all the findings and update the document clearly" (after an
external AI review of the repo confirmed the deferred items).

**Done:** Every item the 2026-07-22 audit left open is now fixed in
`scripts/orchestrate.py` + `scripts/roster.yaml`, and all docs updated to match
(`README.md`, `FEATURES.md`, `SECURITY_AUDIT.md`, `references/model-roster.md`;
`SKILL.md` needed no changes — it makes no delivery-mechanics claims):

- `shell=True` removed — all CLI calls run as `shlex.split()` argv lists with
  `shell=False`; `run_api` rejects non-HTTPS `base_url`.
- ARG_MAX / silent degradation — inline delivery is capped at 100,000 bytes with a
  loud, actionable error; `parse_findings()` now returns
  `None` for unparseable output so failed workers are excluded and named, never
  counted as "0 findings"; stderr reports "N/M workers contributed."
  (Delivery note: `gemini` briefly moved to stdin, but the standalone Gemini CLI's
  subscription login turned out to be dead — see the AGY entry below; the Gemini
  slot is inline again via AGY, under the same 100 KB cap.)
- `read_target()` — `/dev/stdin` and `-` read as streams (the documented
  piped-diff workflow now works); typo'd paths are loud errors; the 180k cap is
  uniform across files/dirs/pipes; symlinks escaping the target root are skipped
  and reported.
- Report written `0600` (owner-only); CLI stderr / API error bodies / organizer
  exception strings are secret-scrubbed before reaching the report or a prompt.
- Token-strip corruption gone by construction (per-argument substitution, no
  post-hoc regex); typos in `--organizer`/`--workers` give clean errors.

**Verification:** 23-check smoke suite (delivery paths, shell-injection safety,
content preservation, parse edge cases, pipe/stdin, symlink escape, caps, a full
end-to-end run with stub CLIs, report permissions) — all passing. No real model
calls were made during testing.

**Judgment call — enhancements NOT applied:** the external review also suggested
new features (`--dry-run`, SARIF output, per-model context caps, weighted
agreement, structured-output modes, TruffleHog/Gitleaks backend). These are
additions, not bug fixes, so they were recorded in `SECURITY_AUDIT.md`'s roadmap
(item 8) rather than built unasked.

## 2026-07-24 (later) — Gemini slot moved from the `gemini` CLI to AGY (Antigravity)

**Request:** "for gemini we use AGY not gemini — inside AGY we have gemini models."

**Verified live against the installed CLIs (tiny real calls):**
- The standalone `gemini` CLI rejects this machine's subscription login:
  `IneligibleTierError: ... migrate to the Antigravity suite`. Stdin delivery
  mechanically worked, but auth is dead — so Gemini can't run through `gemini`.
- `agy --print '<prompt>'` works headlessly (positional argv prompt). It has no
  stdin or file prompt mode — piped stdin is ignored and it launches interactive
  mode instead.
- **AGY bug found:** adding `--model <any>` or `--effort high` to `--print` makes
  AGY drop the prompt and answer about the setting instead (reproduced with
  several values, `--model=x` form included). So the roster must call bare
  `agy --print {prompt}`; the worker runs AGY's default model (self-reports
  "Gemini 3.6 Flash (High)"). `agy models` lists selectable models
  (`gemini-3.1-pro-high`, `gemini-3.6-flash-high`, …) but picking one headlessly
  is blocked by that bug — choose the default inside AGY itself.

**Done:** `roster.yaml` gemini worker → `cmd: 'agy --print {prompt}'`,
`model: agy-default`, `max_chars: 80000` (inline, under the 100 KB cap);
docs updated (`README.md`, `FEATURES.md`, `SKILL.md`,
`references/model-roster.md`, `SECURITY_AUDIT.md`). No `orchestrate.py` change
needed — `{prompt}` inline delivery and the 100 KB guard already cover AGY.

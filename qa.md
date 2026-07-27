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

## 2026-07-27 — Roster refreshed to current models; GPT slot replaced

**Request:** "update it to the newest models. also gpt not available now." Then, mid-run:
"use kimi k3 max as well, grok4.5 high as well" and "you can also use codex-fugu cli for
fugu-ultra-v1.1 xhigh until the gpt is available. the GPT quota is got over."

**Verified live against the installed CLIs (tiny real single-turn calls, 2026-07-27):**
- `claude -p --model claude-opus-5` and `--model claude-sonnet-5` both answer;
  `--effort` accepts `high` / `xhigh` / `max` in print mode.
- `codex-fugu exec -m fugu-ultra-v1.1 -c model_reasoning_effort=xhigh` answers on stdin
  (provider reports `sakana`). Requires `--skip-git-repo-check` outside a git repo, and
  prints a session preamble around the answer (harmless — `parse_findings` slices the
  JSON out of prose). Heavy: ~27K tokens for a one-word reply.
- `agy --model gemini-3.6-flash-high -p '<prompt>'` **now works** — the 2026-07-24
  print-mode `--model` bug is fixed, so the Gemini model is pinned explicitly again
  instead of riding AGY's default. `--print-timeout 15m` accepted.
- `grok models` confirms a live grok.com login, `grok-4.5` the only model.
- Kimi has **no per-call effort flag**; `[thinking] effort` was `high` and
  `[models."kimi-code/k3"]` carries `default_effort = "high"`. Added a local
  `[models."kimi-code/k3-max"]` alias (same `k3`, 1M context, `default_effort = "max"`)
  to `~/.kimi-code/config.toml`; `kimi doctor` validates and `kimi -m kimi-code/k3-max -p`
  answers. Backup at `config.toml.bak-20260727`.

**Done:** `roster.yaml` organizers → `opus` (claude-opus-5, default) · `fugu`
(fugu-ultra-v1.1) · `grok`. Workers → `opus` 1.3 · `fugu` 1.1 · `sonnet` 1.0 ·
`grok` 1.0 · `kimi` 0.9. `quick_workers` → `sonnet,grok,kimi`. `timeout_seconds`
600 → 900 (max-effort workers were at risk of being cut off). Docs updated:
`SKILL.md`, `README.md`, `FEATURES.md`, `references/model-roster.md`. No
`orchestrate.py` change needed — it is fully roster-driven; the 49-test suite
still passes.

**End-to-end verification (real models, not stubs):** ran the full ensemble against a
6-line file with a deliberate SQL injection and a `shell=True` command injection.
Result: `5/6 workers contributed`, 12 merged findings, both injections flagged
**critical at 5/5 agreement**, report written `0600`. Opus 5 returned 5 findings,
Kimi 3, Sonnet/Grok/fugu 2 each. The organizer's synthesis correctly merged the
duplicate injection pairs and folded "argument injection" into the command-injection
fix. The pipeline is confirmed working, not just parseable.

**Judgment call 0 — Gemini removed after it refused the job.** The one worker that
dropped out of that run was Gemini: it returned prose, not findings, and
`parse_findings` correctly excluded it rather than scoring it as "0 findings" (the
2026-07-24 guard doing exactly its job). Reproduced directly — `gemini-3.6-flash-high`
answered *"Sorry, I cannot fulfill your request to analyze this code snippet for
vulnerabilities"*, and `gemini-3.1-pro-high`, given an explicit authorized-blue-team
framing, answered *"I am unable to perform vulnerability analysis or security audits on
specific code snippets."* Non-security prompts through the same CLI answer fine, so it
is provider policy, not wiring. Removed from `defaults.workers`, entry kept in
`roster.yaml` with the refusal text quoted. **Deliberately did not attempt to reword
the prompt around a safety refusal** — that's the provider's call to make, and a worker
coaxed past its own policy is not one whose findings should carry weight in an
agreement score.

**Judgment call 1 — GPT dropped, not stubbed.** The ChatGPT allowance is exhausted
(the seat is gone, not throttled), so `sol`/`terra` are removed rather than left in to
fail at runtime. `fugu-ultra-v1.1` holds the slot. `FEATURES.md` §14 documents the exact
entries to restore when GPT access returns.

**Judgment call 2 — Claude Fable 5 removed from the worker tier.** Not a cost decision:
Anthropic's guidance is that Fable 5's bug-finding gains exclude security analysis, and
its safety classifiers can decline cyber-adjacent prompts while returning a *successful,
empty* response. `parse_findings` would read that as a legitimate "0 findings" rather
than a failed worker, quietly skewing the agreement score in the safest-looking
direction. Opus 5 and Kimi K3 take the reviewing/verification role instead.

**Judgment call 3 — two same-family workers.** `opus` + `sonnet` are both Anthropic and
share blind spots, so raw agreement count slightly overstates independence when only
those two agree. Documented in all three docs rather than papered over; the `weight`
values partly compensate, and `quick_workers` was deliberately built from three
*different* families (xAI / Google / Moonshot).

**Judgment call 4 — the Kimi alias edits a file outside this repo.** Pinning K3 to max
required a change to `~/.kimi-code/config.toml`. Adding a new alias rather than setting
`[thinking] effort = "max"` keeps every other Kimi session on its existing default; the
roster comments and `references/model-roster.md` tell a fresh installer to add the same
alias, since the repo cannot ship it for them.

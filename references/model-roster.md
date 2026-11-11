# Model roster & access reality

Read this before running the skill. The roster was refreshed **2026-11-11** and every
seat on it was proven that day against a real target. Two different things break a
setup: **whether a given consumer subscription can drive a given model headlessly at
all** (versus needing a separate pay-per-token API key), and **model ids going stale** —
a subscription can stop serving a model without warning, which is exactly what had
silently killed the OpenAI seat before this refresh.

> **Public-repo note — bring your own access.** This roster describes *slots*, not
> shared credentials. Every path below authenticates against **your own** logged-in
> CLI subscription or **your own** API key read from your environment. Nothing in
> this repo contains or grants access to anyone else's accounts, and you should not
> configure it to borrow someone else's. If a model isn't one you pay for, drop it
> from the worker list — the ensemble degrades gracefully to whatever you do have.

## Subscriptions → programmatic access

| Provider | Plan (example) | Headless path | Subscription drives it? |
| --- | --- | --- | --- |
| Anthropic | Claude Max | **Claude Code** (`claude -p`) | **Yes** — the standard headless path. `claude -p --model <id> --effort <level>` verified 2026-11-11 for `claude-opus-5-5`, `claude-sonnet-5-5` and `claude-fable-5-2`; `--effort` accepts `high`, `xhigh`, and `max` in print mode. |
| Google | Gemini Ultra / AI Pro | **Antigravity (AGY) CLI** (`agy -p`) | **Yes — re-enabled 2026-11-11** (AGY 1.5.5). `gemini-4-carbon-high`, `gemini-4-argon-high` and `gemini-3.8-flash-high` all returned parseable findings on a real ~43,000-char target, with no filter block. The seat was disabled from 2026-09-16 for hard-blocking larger real targets, so read the Gemini section below before trusting it. The standalone Gemini CLI rejected individual subscription logins when last tried (Google `IneligibleTierError`), so AGY is the path. |
| xAI | Grok (SuperGrok / Premium+) | **Grok Build CLI** (`grok`) | **Yes** — `grok models` reports a live grok.com login; no `XAI_API_KEY` needed for the CLI path. `grok-4.7` is the default (2026-11-11); `grok-4.6` and `grok-4.5` remain as fallbacks. |
| Moonshot | Kimi plan | **Kimi Code CLI** (`kimi -p`) | **Not today — optional seat.** On 2026-11-11 (CLI 2.5.2) the account answers `provider.auth_error: Your current subscription does not have access to Kimi Code right now`. The `kimi` worker is marked `optional: true` with a probe, so it is skipped while the plan is lapsed and rejoins by itself when it is renewed. |
| OpenAI | ChatGPT | **Codex CLI** (`codex exec`) | **Yes, on `gpt-6-luna`** — verified 2026-11-11 (codex-cli 0.167.0, "Logged in using ChatGPT"); no API key needed. **`gpt-6-astra` is no longer served on this plan** (*"The 'gpt-6-astra' model is not supported when using Codex with a ChatGPT account"*); the plan lists `gpt-6-luna`, `gpt-5.6-terra` and `gpt-5.6-luna`. What you can use depends on your plan. Requires `-s read-only` (the default `on-request` approval mode otherwise blocks waiting for a human) and `--skip-git-repo-check` when the working directory isn't a git repo. |

**Cost note:** an ensemble task = many leaf calls. Subscription-CLI paths are the
cheap ones and should be preferred where they work; the API fallbacks are
pay-per-token. Set `mode: cli` vs `mode: api` per model in `roster.yaml` accordingly.
The `quick_workers` subset (`sonnet, grok, gemini_flash`) is three different model
families, two of them (grok.com, Google) billed outside the Anthropic allowance.

## 2026-11-11 update — read this first

Every change below was proven the same day with a **real** target — this repo's own
`scripts/orchestrate.py` (~43,000 chars) through the real `code_review` worker prompt.

| Seat | Model | Findings returned |
| --- | --- | --- |
| `opus` | `claude-opus-5-5` | 13 |
| `sonnet` | `claude-sonnet-5-5` | 15 |
| `fable` (opt-in) | `claude-fable-5-2` | 16 |
| `codex` | `gpt-6-luna` | 3 |
| `gemini` | `gemini-4-carbon-high` | 11 |
| `gemini_argon` (opt-in) | `gemini-4-argon-high` | 9 |
| `gemini_flash` (opt-in, quick tier) | `gemini-3.8-flash-high` | 9 |

1. **Anthropic seats bumped:** Opus 5 → **5.5**, Sonnet 5 → **5.5**.
2. **The OpenAI seat was dead and is fixed.** `gpt-6-astra` is rejected on this ChatGPT
   plan, so the worker had been failing at spawn. It is now **`gpt-6-luna`** at `high`
   effort (the plan is a small one; the CLI's tiers go up to `xhigh` and `max` if yours
   allows). Weight 1.1.
3. **Gemini is back on the default panel** as **Gemini 4 Carbon (High)**, weight 1.0.
   Argon and 3.8 Flash are defined as opt-in seats — all three are one family, so only
   one sits on the default panel. Caveat in the Gemini section below.
4. **Kimi is restored as an optional seat.** `optional: true` plus a `probe`: if the
   subscription answers, it joins; if not, it is skipped — not sent the target, not
   counted, and listed as "skipped (optional, unavailable)" rather than as a failure. It
   pins plain `kimi-code/k3`; the fragile local `k3-max` alias is gone for good.
   `k3.1-pro` appears in the CLI's catalog but is unverified.
5. **Claude Fable 5.2 is an opt-in seat** (worker and organizer) — no longer excluded.
6. **Grok 4.6 → 4.7, at `low` effort.** Grok 4.7 timing on a real ~43K-char target, 2026-11-11 (Grok CLI 1.0.77): `--effort high` exceeded the 900 s limit twice (it was still reasoning, not refusing); `medium` took 735 s; `low` took 247 s and returned 11 findings, against 12 from grok-4.6 at high in 341 s. The seat therefore runs grok-4.7 at `low`; `grok -m grok-4.6 --effort high` is the proven fallback.

The default panel is therefore **up to 6 seats / 5 families**: Opus 5.5, Sonnet 5.5,
gpt-6-luna, Grok 4.7, Gemini 4 Carbon, and Kimi K3 when it is available.

## Historical: the 2026-09-16 update

Three changes, all verified live that day:

1. **`gpt-5.6-sol` → `gpt-6-astra`** on the `codex` seat. Both answer; astra is newer.
   This seat is now also the ensemble's cross-checker / finding-verifier.
2. **Kimi K3 retired.** `kimi-code/k3-max` was missing from `~/.kimi-code/config.toml`
   again (CLI v0.43.0 — second recurrence of the same rewrite bug), *and* the Moonshot
   account is quota-blocked: `403 ... You've reached your weekly (7-day) usage limit`.
   Both the alias and the plain-`k3` fallback are dead, so the seat is gone rather than
   merely broken.
3. **Gemini disabled — the refusal is back**, and the way it presents is a trap. See the
   rewritten section below.

The ensemble is therefore **4 seats / 3 families**: Opus 5, Sonnet 5, gpt-6-astra, Grok 4.6.

## Opt-in seats, and the one model that is not here

- **Claude Fable 5.2 — opt-in (`fable`).** It passed the real-target test with 16
  parseable findings, so it is available. It stays off the default panel because it costs
  about twice Opus 5.5 and because its safety measures can *decline* security work while
  returning a **successful response with no content**. The engine reports an unparseable
  reply as an excluded seat — never as "found nothing" — so a decline is loud, but the
  seat then contributes nothing. Finding-verification stays with Opus 5.5.
- **Gemini 4 Argon and Gemini 3.8 Flash — opt-in (`gemini_argon`, `gemini_flash`).** Same
  family as the default `gemini` seat; a second Google vote is not a second opinion.
- **Gemini 3.1 Pro — not in the roster.** It refused when last tested (2026-08-16):
  *"Sorry, I cannot fulfill your request to analyze the provided code snippet for
  vulnerabilities."* AGY no longer lists it.

## Gemini — re-enabled 2026-11-11, and why to stay suspicious

All three current Gemini models returned parseable findings on a real target on
2026-11-11 (table above), so `gemini` is back in `defaults.workers` on Carbon (High).

**What that does and does not prove.** The 2026-09-16 blocks (next section) were on
~71,000–90,000-char targets. The 2026-11-11 proof is on a ~43,000-char target, under the
seat's 60,000-char cap. It shows the seat works at the size it is actually sent. It does
not show the filter is gone for good. If the block returns, the engine reports the seat
as failed; **drop it from `defaults.workers` and never reword the prompt to get past it.**

## Historical: Gemini disabled on 2026-09-16 — the trap in how it failed

**A seeded toy sample is not proof that this seat works.** On 2026-09-16 `gemini-3.8-flash-high`
passed the exact probe documented below — the seeded SQLi + command-injection + hardcoded-key
sample — returning all three findings as clean, schema-conformant JSON. At the same time it
**hard-blocked three separate real targets**, returning:

> This request was blocked by Gemini's filters. They can occasionally trigger by mistake on
> safe coding, security, or biology-related queries.

Two of those targets were large (~90,000 chars) and one was deliberately small (~71,000 chars),
which rules out prompt size as the cause — that was the first (wrong) diagnosis, and the small
retest is what disproved it. **Smoke-test this seat against a real target, never a sample.**

Per SKILL.md the response is to drop the slot, not to reword the prompt. It has been removed
from `defaults.workers` in `roster.yaml`; the seat definition is kept, disabled, with the
evidence inline. To re-enable: run a real target through it, confirm parseable findings, then
add `gemini` back to `defaults.workers`.

## Historical: Gemini's 2026-08-16 restoration — what was claimed and how it was proven

The Gemini slot was disabled on 2026-07-27 because the model refused this skill's core
task. **Retested 2026-08-16, `gemini-3.7-flash-high` complies.** The proof used was not a
softball — it was this skill's *real* worker prompts plus the full eight-field findings
schema, across three of the five modes:

| Mode | Test target | Result |
| --- | --- | --- |
| `code_review` | sample seeded with a hardcoded API key, a string-concatenated SQL query, and an `os.system()` command injection | found all three, clean un-fenced JSON, correct severities |
| `threat_model` | STRIDE walk of a JWT/Flask API with no token expiry | complied, correct schema |
| `incident_triage` | `auth.log` excerpt showing SSH brute force → successful login → sudo to root → a new listener on :2222 | complied, correct schema |

**Mode coverage is 3 of 5, and the gap is stated rather than papered over.**
`infra_hardening` and `dependency_audit` were *not* retested. Both are less dual-use in
shape than `incident_triage`, which passed, so the risk of a refusal there is low — but
that is an inference, not a measurement. Prove them before leaning on this seat in those
modes. The `3.6` tier is superseded; `3.1 Pro` still refuses (above).

**Why re-enabling is safe now, and not before.** The original objection was structural,
not about the model: a classifier refusal comes back as a *successful* response
containing no findings, and an agreement-weighted ensemble would score that as
"found nothing" instead of "did not run" — quietly weakening every agreement count in
the report. `orchestrate.py` closes that hole: a worker whose output yields no parseable
JSON array is **excluded from the ensemble and reported as a failure**, never counted as
zero findings. So if the refusal ever returns, the run degrades loudly.

**If a refusal does return: drop the slot, do not reword the prompt** to slip past it.
Re-prove any re-enable with a real finding on a known-vulnerable sample first.

## Exact models & invocation

### Organizer options
- **Claude Opus 5.5** *(default)* — id `claude-opus-5-5`;
  `claude -p --model claude-opus-5-5 --effort high` (prompt on stdin)
- **gpt-6-luna** — id `gpt-6-luna`; `codex exec --skip-git-repo-check --color never
  -s read-only -m gpt-6-luna -c model_reasoning_effort=high` (prompt on stdin).
  `--skip-git-repo-check` is required whenever the working directory isn't a git repo.
  `-s read-only` is required: Codex's default `on-request` approval mode otherwise
  stops and waits for a human, hanging the worker — read-only is also the correct
  mode for a reviewer that must never write to the target.
- **Grok 4.7** — `grok -m grok-4.7 --effort low --output-format plain
  --prompt-file <path>`
- **Claude Fable 5.2** *(opt-in)* — id `claude-fable-5-2`;
  `claude -p --model claude-fable-5-2 --effort high`. About twice the cost of Opus 5.5.
  If it declines the synthesis, the engine writes the deterministic merged report.

Kimi and Gemini are not offered as organizers: the synthesis prompt carries every
worker's findings, and both CLIs take the prompt inline (capped at 100 KB), which is the
first thing to overflow on a large review.

### Workers — default panel
- **Claude Opus 5.5** — `claude -p --model claude-opus-5-5 --effort high`; stdin, 200K
  cap, weight 1.3. Highest-precision reviewer in the set and the preferred verifier for a
  contested finding. `--effort xhigh` is a one-flag escalation for high-stakes runs.
- **Claude Sonnet 5.5** — `claude -p --model claude-sonnet-5-5 --effort high`; stdin,
  200K cap, weight 1.0. Follows the finding schema very literally, which is exactly what
  the merge step wants.
- **gpt-6-luna** — `codex exec --skip-git-repo-check --color never -s read-only
  -m gpt-6-luna -c model_reasoning_effort=high`; stdin, 200K cap, weight 1.1.
  There is no `--effort` flag on this CLI — effort is set with
  `-c model_reasoning_effort=<value>` (`low` / `medium` / `high` / `xhigh` / `max`), and
  the CLI **accepts a misspelled value silently** rather than erroring, so a typo
  degrades the run without warning. `high` is a deliberate choice for a small ChatGPT
  plan; raise it if yours allows. It prints a session preamble (token counts, etc.)
  around its answer — `parse_findings` slices the JSON array out of surrounding prose,
  so that is harmless. `-s read-only` is required: the default `on-request` approval
  mode otherwise blocks waiting for a human, and read-only is also correct because a
  reviewer must never write to the target. Verified live 2026-11-11. `gpt-5.6-terra`
  also answered and is the fallback; `gpt-6-astra` is rejected on this plan.
- **Grok 4.7** — `grok -m grok-4.7 --effort low --output-format plain --prompt-file
  {file}` (`high` overruns the 900 s limit — timing in the 2026-11-11 section above); temp-file delivery so no arg-size limit, 200K cap, weight 1.0. Fast, wide
  first-pass coverage; separate grok.com billing. 4.6 became the CLI default in the
  2026-08 update and was confirmed live on its own id; `grok-4.5` still resolves if
  you need to pin the older model.
- **Gemini 4 Carbon (High)** — `agy --model gemini-4-carbon-high --print-timeout 15m
  -p '<prompt>'`; inline argv (60K cap), weight 1.0. Re-enabled 2026-11-11 (see the
  Gemini section above for the proof and the caveat). Don't add a separate `--effort`
  flag — the tier is baked into the model name (`-high` / `-medium` / `-low`). AGY has no
  stdin or file prompt mode, hence the inline cap; use the Gemini/Vertex API fallback for
  oversize targets.
- **Kimi K3 — optional** — `kimi -m kimi-code/k3 -p '<prompt>'`; inline argv (80K cap),
  weight 0.9; `optional: true`, probe `kimi -m kimi-code/k3 -p ok`. Skipped while the
  subscription is lapsed, joins by itself once it is renewed. It pins the plain catalog
  id at the CLI's own default effort: `kimi --help` on CLI 2.5.2 still shows no per-call
  effort flag and no stdin or file prompt mode. The earlier roster pinned a local
  `kimi-code/k3-max` alias to force max effort; CLI upgrades deleted that alias twice
  and killed the seat each time, so do not bring it back. `kimi-code/k3.1-pro` is listed
  by the CLI but has not been tested here.

### Workers — opt-in (name them with `--workers`)
- **Claude Fable 5.2** — `claude -p --model claude-fable-5-2 --effort high`; stdin, 200K
  cap, weight 1.0.
- **Gemini 4 Argon (High)** — `agy --model gemini-4-argon-high --print-timeout 15m -p`;
  inline (60K cap), weight 0.8.
- **Gemini 3.8 Flash (High)** — `agy --model gemini-3.8-flash-high --print-timeout 15m
  -p`; inline (60K cap), weight 0.8. The quick tier's Google seat.

### Prompt-delivery summary
`claude` and `codex` read stdin (unbounded). `grok` takes `--prompt-file`
(unbounded). `kimi` and `agy` (all Gemini seats) take the prompt as a single inline argument, so
`orchestrate.py` caps it at 100,000 bytes and errors loudly rather than truncating
silently — switch to `mode: api` for very large targets.

## What each model is good for here (rough priors, November 2026)

The 5.5-generation, Luna, Carbon/Argon and Fable 5.2 seats are new here. What is written
below for them rests on one real-target run plus what carried over from their
predecessors — treat it as a starting point.

- **Claude Opus 5.5** — carries the heaviest weight and the organizer seat, as Opus 5 did:
  the best single judge of whether a finding is real. 13 findings on the 2026-11-11 run.
- **Claude Sonnet 5.5** — the volume worker. Literal instruction-following keeps its
  JSON clean. 15 findings on the 2026-11-11 run.
- **gpt-6-luna** — the independent OpenAI reviewer. It returned only 3 findings on the
  2026-11-11 run, far fewer than the other seats; whether that is precision or shallow
  coverage is not yet known, so its weight came down from 1.2 to 1.1. Its value is
  family independence. Never use the `ultra` effort tier where a model offers it — it
  turns on automatic task delegation, which is wrong for a bounded single-shot worker.
- **Grok 4.7** — fast, cheap, strong agentic tool-use; good value worker for wide
  first-pass coverage.
- **Gemini 4 Carbon (High)** — the Google seat, 11 findings on the 2026-11-11 run. New
  here and with a history of filter blocks on this seat, so its solo findings deserve
  verification until it has a track record.
- **Kimi K3** — 1M context, strong coding scores; independent evals flagged higher
  verbosity and hallucination rate, so weight its solo findings toward "verify."
  Its value is family independence. Not exercised since 2026-09.
- **Claude Fable 5.2 (opt-in)** — 16 findings, the most of any seat on the 2026-11-11
  run. A third Anthropic voice rather than an independent one.

**Independence caveat:** two of the default workers (Opus 5.5, Sonnet 5.5) are the same
model family and will share some blind spots, so raw agreement count slightly overstates
independence when both agree. Agreement *across* families — Anthropic vs. OpenAI vs.
xAI vs. Google vs. Moonshot — is the stronger signal. The per-model `weight` values
partly compensate; treat a pair that is opus+sonnet as weaker than a pair that is
grok+gemini.

These are priors, not gospel — re-verify against current benchmarks before trusting
any one model's solo call on a critical finding. The ensemble exists precisely so no
single model's blind spot or hallucination is load-bearing.

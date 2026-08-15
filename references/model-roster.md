# Model roster & access reality

Read this before running the skill. The models are all real and current (roster
refreshed **2026-08-16**, every invocation below smoke-tested live on that date); the
thing most likely to break your setup is not the model IDs but **whether a given
consumer subscription can actually drive a given model headlessly, or whether you
need a separate pay-per-token API key.** Those are different products.

> **What changed on 2026-08-16.** Grok moved `4.5 → 4.6`. Gemini moved
> `3.6 Flash → 3.7 Flash` **and came back into the worker pool** — its
> security-review refusal has lifted on the Flash tier (retested against this skill's
> real prompt; details below). And the Kimi seat was found **silently broken** — a CLI
> upgrade had wiped the required local `kimi-code/k3-max` alias, so that worker had
> been dying at spawn on every run; the alias is restored and re-verified. The
> Anthropic and OpenAI seats were already on their newest ids and did not move.

> **Public-repo note — bring your own access.** This roster describes *slots*, not
> shared credentials. Every path below authenticates against **your own** logged-in
> CLI subscription or **your own** API key read from your environment. Nothing in
> this repo contains or grants access to anyone else's accounts, and you should not
> configure it to borrow someone else's. If a model isn't one you pay for, drop it
> from the worker list — the ensemble degrades gracefully to whatever you do have.

## Subscriptions → programmatic access

| Provider | Plan (example) | Headless path | Subscription drives it? |
| --- | --- | --- | --- |
| Anthropic | Claude Max | **Claude Code** (`claude -p`) | **Yes** — the standard headless path. `claude -p --model <id> --effort <level>` is verified working for `claude-opus-5` and `claude-sonnet-5`; `--effort` accepts `high`, `xhigh`, and `max` in print mode. |
| Google | Gemini Ultra / AI Pro | **Antigravity (AGY) CLI** (`agy -p`) | **Yes, as of 2026-08-16** — the refusal that disabled this slot has lifted on the **Flash** tier. `gemini-3.7-flash-high` answers the real ensemble prompt with schema-conformant findings. `gemini-3.1-pro-high` **still refuses**. The standalone Gemini CLI separately still rejects individual subscription logins (Google `IneligibleTierError`), so AGY is the only path. |
| xAI | Grok (SuperGrok / Premium+) | **Grok Build CLI** (`grok`) | **Yes** — `grok models` reports a live grok.com login; no `XAI_API_KEY` needed for the CLI path. `grok-4.6` is now the default; `grok-4.5` remains as a legacy fallback. |
| Moonshot | Kimi plan | **Kimi Code CLI** (`kimi -p`) | **Yes** — OAuth-logged-in CLI, no API key needed. **But the `k3-max` alias is local-only and CLI upgrades delete it** — see the Kimi worker entry. Moonshot's OpenAI-compatible API is the fallback for oversize targets. |
| OpenAI | ChatGPT | **Codex CLI** (`codex exec`) | **Yes** — re-verified 2026-08-16, logged in via the ChatGPT subscription (`codex login status` reports "Logged in using ChatGPT"); no API key needed. Serves `gpt-5.6-sol` as the `codex` seat — still the top-priority frontier model in the CLI's catalog. Requires `-s read-only` (the default `on-request` approval mode otherwise blocks waiting for a human) and `--skip-git-repo-check` when the working directory isn't a git repo. |

**Cost note:** an ensemble task = many leaf calls. Subscription-CLI paths are the
cheap ones and should be preferred where they work; the API fallbacks are
pay-per-token. Set `mode: cli` vs `mode: api` per model in `roster.yaml` accordingly.
The `quick_workers` subset (`sonnet, grok, kimi`) is three different model families,
two of them (grok.com, Moonshot) billed outside the Anthropic allowance.

## Models deliberately NOT here

- **Claude Fable 5.** Anthropic's own guidance is that Fable 5's bug-finding gains
  **exclude security-focused analysis**, and that its safety classifiers can *decline*
  cyber-adjacent requests while returning a **successful response with no content**.
  A worker that silently returns nothing is the single worst failure mode for an
  agreement-weighted ensemble — it reads as "found nothing" rather than "did not run."
  Security reviewing and finding-verification go to Opus 5 or Kimi K3 instead.
- **Gemini 3.1 Pro, via AGY.** Retested 2026-08-16 and it **still refuses**:
  *"Sorry, I cannot fulfill your request to analyze the provided code snippet for
  vulnerabilities."* The Flash tier's fix did **not** extend to Pro. Do not promote
  `gemini-3.1-pro-high` into a worker slot.

## Gemini is back — what changed and how it was proven

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
- **Claude Opus 5** *(default)* — id `claude-opus-5`;
  `claude -p --model claude-opus-5 --effort high` (prompt on stdin)
- **GPT-5.6 Sol** — id `gpt-5.6-sol`; `codex exec --skip-git-repo-check --color never
  -s read-only -m gpt-5.6-sol -c model_reasoning_effort=xhigh` (prompt on stdin).
  `--skip-git-repo-check` is required whenever the working directory isn't a git repo.
  `-s read-only` is required: Codex's default `on-request` approval mode otherwise
  stops and waits for a human, hanging the worker — read-only is also the correct
  mode for a reviewer that must never write to the target.
- **Grok 4.6** — `grok -m grok-4.6 --effort high --output-format plain
  --prompt-file <path>`

Kimi is not offered as an organizer: the synthesis prompt carries every worker's
findings, and Kimi's CLI takes the prompt inline (capped at 100 KB), which is the
first thing to overflow on a large review.

### Workers
- **Claude Opus 5** — `claude -p --model claude-opus-5 --effort high`; stdin, 200K cap,
  weight 1.3. Highest-precision reviewer in the set and the preferred verifier for a
  contested finding. `--effort xhigh` is a one-flag escalation for high-stakes runs.
- **Claude Sonnet 5** — `claude -p --model claude-sonnet-5 --effort high`; stdin,
  200K cap, weight 1.0. Near-Opus quality on code review at lower cost; follows the
  finding schema very literally, which is exactly what the merge step wants.
- **GPT-5.6 Sol** — `codex exec --skip-git-repo-check --color never -s read-only
  -m gpt-5.6-sol -c model_reasoning_effort=xhigh`; stdin, 200K cap, weight 1.2.
  Heavy: a trivial prompt still burns ~20K tokens at `xhigh`. There is no `--effort`
  flag on this CLI — effort is set with `-c model_reasoning_effort=<value>` (`low` /
  `medium` / `high` / `xhigh`), and the CLI **accepts a misspelled value silently**
  rather than erroring, so a typo degrades the run without warning. It prints a
  session preamble (token counts, etc.) around its answer — `parse_findings` slices
  the JSON array out of surrounding prose, so that is harmless. `-s read-only` is
  required: the default `on-request` approval mode otherwise blocks waiting for a
  human, and read-only is also correct because a reviewer must never write to the
  target. Verified live 2026-07-31, logged in via the ChatGPT subscription.
- **Grok 4.6** — `grok -m grok-4.6 --effort high --output-format plain --prompt-file
  {file}`; temp-file delivery so no arg-size limit, 200K cap, weight 1.0. Fast, wide
  first-pass coverage; separate grok.com billing. 4.6 became the CLI default in the
  2026-08 update and was confirmed live on its own id; `grok-4.5` still resolves if
  you need to pin the older model.
- **Gemini 3.7 Flash (High)** — `agy --model gemini-3.7-flash-high --print-timeout 15m
  -p '<prompt>'`; inline argv (80K cap), weight 0.8. **Re-enabled 2026-08-16** after the
  security-review refusal lifted on this tier (see the section above for the proof and
  the caveat). Don't add a separate `--effort` flag — the tier is baked into the model
  name (`-high` / `-medium` / `-low`). AGY has no stdin or file prompt mode, hence the
  inline cap; use the Gemini/Vertex API fallback for oversize targets. Weighted lightest
  in the pool because the seat is newly restored — raise it once it has a track record.
- **Kimi K3 at max** — `kimi -m kimi-code/k3-max -p '<prompt>'`; inline argv (80K cap),
  weight 0.9. **The Kimi CLI has no per-call effort flag**, so "K3 max" has to come
  from config: `kimi-code/k3-max` is a local alias in `~/.kimi-code/config.toml` —
  same `k3` model and 1M context as the stock `kimi-code/k3`, but with
  `default_effort = "max"`. Copy the `[models."kimi-code/k3"]` block, rename it, set
  `default_effort = "max"`, then run `kimi doctor` to validate. Without that alias the
  worker fails with an unknown-model error. Setting `[thinking] effort = "max"` works
  too but changes every Kimi session globally, which the alias avoids.

  > **This alias is the most fragile thing in the roster — check it before a big run.**
  > It exists only in your local config, and a Kimi CLI upgrade **rewrites that file
  > from its own model catalog and silently drops the alias.** That is exactly what
  > happened between 2026-08-01 and 2026-08-16 (caught on CLI v0.36.0): the worker had
  > been failing at spawn on *every* run with `error: failed to run prompt: Model
  > "kimi-code/k3-max" is not configured in config.toml`, and because a dead worker is
  > correctly excluded rather than counted as zero findings, the symptom was a quietly
  > four-worker ensemble rather than an obvious crash. One-line pre-flight:
  > `kimi -m kimi-code/k3-max -p "ok"`. If it errors, re-add the block. The
  > always-works fallback is plain `kimi-code/k3`, which runs at `high`, not `max`.

### Prompt-delivery summary
`claude` and `codex` read stdin (unbounded). `grok` takes `--prompt-file`
(unbounded). `kimi` and `agy` take the prompt as a single inline argument, so
`orchestrate.py` caps it at 100,000 bytes and errors loudly rather than truncating
silently — switch to `mode: api` for very large targets.

## What each model is good for here (rough priors, August 2026)

- **Claude Opus 5** — high precision *and* high recall on code review, strong on
  multi-file reasoning. Best single judge of whether a finding is real; that's why it
  carries the heaviest weight and the organizer seat.
- **Claude Sonnet 5** — the volume worker. Literal instruction-following keeps its
  JSON clean; near-Opus on code review at meaningfully lower cost.
- **GPT-5.6 Sol** — an independent non-Anthropic reviewer, strong on code and diffs,
  and safe for security work; deep, slow, expensive-per-call reasoning at `xhigh`.
  The Codex CLI has since added `max` and `ultra` above `xhigh` — `ultra` also turns on
  automatic task delegation, which is wrong for a bounded single-shot worker, so if you
  escalate this seat go to `max` and leave `ultra` alone.
- **Grok 4.6** — fast, cheap, strong agentic tool-use; good value worker for wide
  first-pass coverage.
- **Kimi K3 (max)** — 1M context, strong coding scores; independent evals flag higher
  verbosity and hallucination rate, so weight its solo findings toward "verify."
  Its value is family independence — its blind spots differ from everyone else's.
- **Gemini 3.7 Flash (High)** — the cheapest and fastest seat, and the fifth
  independent family. Newly restored, so it carries the lightest weight (0.8) and its
  solo findings deserve verification until it has a track record here. A Flash-tier
  model is a breadth worker, not a depth one — expect it to catch the obvious classes
  reliably and to miss subtle multi-file logic flaws.

**Independence caveat:** two of the six workers (Opus 5, Sonnet 5) are the same model
family and will share some blind spots, so raw agreement count slightly overstates
independence when both agree. Agreement *across* families — Anthropic vs. OpenAI vs.
xAI vs. Moonshot vs. Google — is the stronger signal. The per-model `weight` values
partly compensate; treat a 2/6 that is opus+sonnet as weaker than a 2/6 that is
grok+kimi.

These are priors, not gospel — re-verify against current benchmarks before trusting
any one model's solo call on a critical finding. The ensemble exists precisely so no
single model's blind spot or hallucination is load-bearing.

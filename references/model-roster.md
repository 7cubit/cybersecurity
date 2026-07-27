# Model roster & access reality

Read this before running the skill. The models are all real and current (roster
refreshed **2026-07-27**, every invocation below smoke-tested live on that date);
the thing most likely to break your setup is not the model IDs but **whether a given
consumer subscription can actually drive a given model headlessly, or whether you
need a separate pay-per-token API key.** Those are different products.

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
| Sakana (via Codex CLI) | — | **`codex-fugu exec`** | **Yes** — a Codex CLI build pointed at provider `sakana`, serving `fugu-ultra-v1.1`. Verified answering at `model_reasoning_effort=xhigh`. Fills the GPT slot while the OpenAI seat is unavailable. |
| Google | Gemini Ultra / AI Pro | **Antigravity (AGY) CLI** (`agy -p`) | **Access yes, task no.** AGY drives Gemini fine, but the model **refuses security review** (see below), so the slot is disabled. The standalone Gemini CLI separately no longer accepts individual subscription logins (Google `IneligibleTierError`). |
| xAI | Grok (SuperGrok / Premium+) | **Grok Build CLI** (`grok`) | **Yes** — `grok models` reports a live grok.com login; no `XAI_API_KEY` needed for the CLI path. `grok-4.5` is the only and default model. |
| Moonshot | Kimi plan | **Kimi Code CLI** (`kimi -p`) | **Yes** — OAuth-logged-in CLI, no API key needed. Moonshot's OpenAI-compatible API is the fallback for oversize targets. |
| OpenAI | ChatGPT | ~~Codex CLI (`codex exec`)~~ | **No — allowance exhausted.** GPT-5.6 Sol/Terra are out of the roster until the seat comes back. Do not route to OpenAI. |

**Cost note:** an ensemble task = many leaf calls. Subscription-CLI paths are the
cheap ones and should be preferred where they work; the API fallbacks are
pay-per-token. Set `mode: cli` vs `mode: api` per model in `roster.yaml` accordingly.
The `quick_workers` subset (`sonnet, grok, kimi`) is three different model families,
two of them (grok.com, Moonshot) billed outside the Anthropic allowance.

## Three models that are deliberately NOT here

- **GPT-5.6 Sol / Terra (Codex).** The ChatGPT allowance is exhausted — the seat is
  gone, not merely rate-limited. `fugu-ultra-v1.1` occupies that slot in the meantime.
  When GPT access returns, re-add `sol` as a worker (`codex exec -m gpt-5.6-sol
  -c model_reasoning_effort=high`, stdin delivery) and `terra` as an organizer.
- **Claude Fable 5.** Anthropic's own guidance is that Fable 5's bug-finding gains
  **exclude security-focused analysis**, and that its safety classifiers can *decline*
  cyber-adjacent requests while returning a **successful response with no content**.
  A worker that silently returns nothing is the single worst failure mode for an
  agreement-weighted ensemble — it reads as "found nothing" rather than "did not run."
  Security reviewing and finding-verification go to Opus 5 or Kimi K3 instead.
- **Gemini, via AGY.** It **refuses this skill's core task.** Tested 2026-07-27 against
  a 6-line SQL-injection/command-injection sample, once through the real ensemble
  prompt and once with an explicit authorized-blue-team framing:
  - `gemini-3.6-flash-high` → *"Sorry, I cannot fulfill your request to analyze this
    code snippet for vulnerabilities."*
  - `gemini-3.1-pro-high` → *"I am unable to perform vulnerability analysis or security
    audits on specific code snippets."*

  Everything else works — the same CLI, login, pinned model and inline prompt delivery
  answer non-security prompts correctly the same day — so this is a provider policy
  decision, not broken wiring. The entry stays in `roster.yaml` (disabled, out of
  `defaults.workers`) so it can be re-enabled if the policy changes or if you wire the
  Gemini/Vertex API directly. **Do not reword the prompt to work around the refusal**;
  if you re-enable it, prove it with a real finding on a known-vulnerable sample first.

## Exact models & invocation

### Organizer options
- **Claude Opus 5** *(default)* — id `claude-opus-5`;
  `claude -p --model claude-opus-5 --effort high` (prompt on stdin)
- **fugu-ultra-v1.1** — `codex-fugu exec --skip-git-repo-check --color never
  -m fugu-ultra-v1.1 -c model_reasoning_effort=xhigh` (prompt on stdin).
  `--skip-git-repo-check` is required whenever the working directory isn't a git repo.
- **Grok 4.5** — `grok -m grok-4.5 --effort high --output-format plain
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
- **fugu-ultra-v1.1** — `codex-fugu exec --skip-git-repo-check --color never
  -m fugu-ultra-v1.1 -c model_reasoning_effort=xhigh`; stdin, 200K cap, weight 1.1.
  Heavy: a one-word prompt still burned ~27K tokens at `xhigh`. It prints a session
  preamble (`provider: sakana`, token counts) around its answer — `parse_findings`
  slices the JSON array out of surrounding prose, so that is harmless.
- **Grok 4.5** — `grok -m grok-4.5 --effort high --output-format plain --prompt-file
  {file}`; temp-file delivery so no arg-size limit, 200K cap, weight 1.0. Fast, wide
  first-pass coverage; separate grok.com billing.
- **Gemini 3.6 Flash (High)** — *disabled; refuses security review, see above.* Kept in
  `roster.yaml` as `agy --model gemini-3.6-flash-high --print-timeout 15m -p '<prompt>'`;
  inline argv (80K cap), weight 0.8. Mechanically it is healthy: the `--model` flag that
  broke print mode on 2026-07-24 (the CLI answered *about* the flag instead of the
  prompt) is fixed as of 2026-07-27, so the model can be pinned rather than left to
  AGY's default. Don't add a separate `--effort` flag — the tier is in the model name.
  AGY has no stdin or file prompt mode, hence the inline cap.
- **Kimi K3 at max** — `kimi -m kimi-code/k3-max -p '<prompt>'`; inline argv (80K cap),
  weight 0.9. **The Kimi CLI has no per-call effort flag**, so "K3 max" has to come
  from config: `kimi-code/k3-max` is a local alias in `~/.kimi-code/config.toml` —
  same `k3` model and 1M context as the stock `kimi-code/k3`, but with
  `default_effort = "max"`. Copy the `[models."kimi-code/k3"]` block, rename it, set
  `default_effort = "max"`, then run `kimi doctor` to validate. Without that alias the
  worker fails with an unknown-model error. Setting `[thinking] effort = "max"` works
  too but changes every Kimi session globally, which the alias avoids.

### Prompt-delivery summary
`claude` and `codex-fugu` read stdin (unbounded). `grok` takes `--prompt-file`
(unbounded). `kimi` (and the disabled `agy` slot) takes the prompt as a single inline
argument, so `orchestrate.py` caps it at 100,000 bytes and errors loudly rather than
truncating silently — switch to `mode: api` for very large targets.

## What each model is good for here (rough priors, July 2026)

- **Claude Opus 5** — high precision *and* high recall on code review, strong on
  multi-file reasoning. Best single judge of whether a finding is real; that's why it
  carries the heaviest weight and the organizer seat.
- **Claude Sonnet 5** — the volume worker. Literal instruction-following keeps its
  JSON clean; near-Opus on code review at meaningfully lower cost.
- **fugu-ultra-v1.1** — deep, slow, expensive-per-call reasoning at `xhigh`. Useful
  as an independent non-Anthropic deep pass while the GPT slot is empty.
- **Grok 4.5** — fast, cheap, strong agentic tool-use; good value worker for wide
  first-pass coverage.
- **Kimi K3 (max)** — 1M context, strong coding scores; independent evals flag higher
  verbosity and hallucination rate, so weight its solo findings toward "verify."
  Its value is family independence — its blind spots differ from everyone else's.

**Independence caveat:** two of the five workers (Opus 5, Sonnet 5) are the same model
family and will share some blind spots, so raw agreement count slightly overstates
independence when both agree. Agreement *across* families — Anthropic vs. Sakana vs.
xAI vs. Moonshot — is the stronger signal. The per-model `weight` values partly
compensate; treat a 2/5 that is opus+sonnet as weaker than a 2/5 that is grok+kimi.

These are priors, not gospel — re-verify against current benchmarks before trusting
any one model's solo call on a critical finding. The ensemble exists precisely so no
single model's blind spot or hallucination is load-bearing.

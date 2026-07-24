# Model roster & access reality

Read this before running the skill. The models are all real and current (verified
July 2026); the thing most likely to break your setup is not the model IDs but
**whether a given consumer subscription can actually drive a given model headlessly,
or whether you need a separate pay-per-token API key.** Those are different products.

> **Public-repo note — bring your own access.** This roster describes *slots*, not
> shared credentials. Every path below authenticates against **your own** logged-in
> CLI subscription or **your own** API key read from your environment. Nothing in
> this repo contains or grants access to anyone else's accounts, and you should not
> configure it to borrow someone else's. If a model isn't one you pay for, drop it
> from the worker list — the ensemble degrades gracefully to whatever you do have.

## The five subscriptions → programmatic access

| Provider | Plan (example) | Headless path | Subscription drives it? |
| --- | --- | --- | --- |
| Anthropic | Claude Max | **Claude Code** (`claude -p`) | **Yes** — the standard headless path. Note: Opus 4.8 is confirmed; whether **Fable 5** is selectable under a *Max* seat vs. requiring API access is the one Anthropic-side item to verify in your model settings. |
| OpenAI | ChatGPT Plus | **Codex CLI** (`codex exec`), auth'd with your ChatGPT account | **Yes** — Plus grants GPT-5.6 **Sol** at medium+ effort, and the "max" reasoning toggle. Terra/Luna also available. |
| Google | Gemini Ultra / AI Pro | **Antigravity (AGY) CLI** (`agy --print`) | **Yes** — AGY is Google's supported subscription path. The standalone **Gemini CLI no longer accepts individual subscription logins** (Google `IneligibleTierError`: "migrate to the Antigravity suite", confirmed on this machine 2026-07-24). |
| xAI | Grok (SuperGrok / Premium+) | **Grok Build CLI** (`grok`) **or** xAI API | **Verify.** Grok Build CLI exists (`x.ai/cli`) and there's free promo usage, but confirm whether it authenticates against your *subscription* or expects an `XAI_API_KEY`. If CLI-subscription auth isn't supported, use the API (separate billing). |
| Moonshot | Kimi plan | **Kimi Code CLI** **or** Moonshot OpenAI-compatible API | **Verify.** Kimi K3 has a CLI and an OpenAI-compatible API (`platform.moonshot.ai`). The cleanest ensemble path is the OpenAI-compatible API since it drops into any OpenAI client; confirm whether your Kimi subscription covers CLI headless use or if you want an API key. |

**Bottom line for the architecture:** three of the five (Claude, Codex, Gemini) are
the ones most orchestrators already drive as subscription-authenticated CLIs in
headless mode. The only genuinely *new* integrations for this skill are **Grok**
(Grok Build CLI or xAI API) and **Kimi** (Kimi Code CLI or the OpenAI-compatible API).
Because Kimi's API is OpenAI-compatible, it slots into any OpenAI-style client with
just a base-URL + key swap, which is the least-effort way to add it.

**Cost note:** an ensemble task = many leaf calls. Subscription-CLI paths are the
cheap ones and should be preferred where they work; the API fallbacks are
pay-per-token. Set `mode: cli` vs `mode: api` per model in `roster.yaml` accordingly,
and consider running the full 5-worker ensemble only for high-stakes reviews, with a
cheaper 2–3 model subset as the default.

## Exact models & invocation

Effort/thinking settings map to the spec: "sol max" → Sol at max effort,
"grok4.5 max" → Grok at high effort, "gemini high" → the AGY default model at its
high setting, "kimi 3" → K3 Max (which currently only runs at max thinking anyway),
"fable 5 max" → Fable 5.

### Organizer options
- **Claude Opus 4.8** — id `claude-opus-4-8`; `claude -p --model claude-opus-4-8`
- **GPT-5.6 Terra** — Codex CLI, model `gpt-5.6-terra`; balanced, good arbiter
- **Grok 4.5** — `grok-4.5`; Grok Build CLI or `POST https://api.x.ai/v1/responses`

### Workers
- **Claude Fable 5** — id `claude-fable-5`; via Claude Code (`--model claude-fable-5`)
  or Anthropic API. (Verify Max-seat selectability, per table above.)
- **GPT-5.6 Sol** — Codex CLI, model `gpt-5.6-sol`, reasoning effort `high`/max;
  or OpenAI API.
- **Grok 4.5** — `grok-4.5`, reasoning effort `high` (dial is low/medium/high, default
  high); Grok Build CLI or xAI API (`/v1/responses`).
- **Gemini (via AGY)** — Antigravity CLI: `agy --print '<prompt>'` (the prompt goes
  **inline as one argv element** — AGY has no stdin or file prompt mode, so
  `orchestrate.py` caps inline delivery at 100,000 bytes and points you to the API
  for larger targets). **Do not add `--model` or `--effort`** — both flags make
  AGY's print mode drop the prompt and answer about the setting instead (verified
  broken 2026-07-24); the worker runs AGY's default model (self-reports "Gemini
  3.6 Flash (High)", 2026-07-24) — pick the model inside AGY itself. The standalone
  `gemini` CLI is dead for individual subscriptions (see table above). API
  alternative: Gemini API / Vertex AI with `GEMINI_API_KEY`.
- **Kimi K3** — Kimi Code CLI (`kimi -m kimi-code/k3 -p <prompt>`; the prompt goes
  **inline as one argv element** — the CLI has no stdin or file prompt mode, so
  `orchestrate.py` caps inline delivery at 100,000 bytes and points you to the API
  for larger targets). Or Moonshot OpenAI-compatible endpoint (base URL
  `https://platform.moonshot.ai/v1` or the current Moonshot base), model id in the
  `kimi-k3` family — **verify the exact API model string** (Moonshot sometimes
  exposes `moonshot-v1`-style aliases). K3 Max, always-on max thinking.

### Non-interactive flags to confirm
The two most common CLIs have stable headless modes (`claude -p`, `codex exec`).
**AGY** headless is `agy --print '<prompt>'` — verified working 2026-07-24, but its
`--model`/`--effort` flags break prompt delivery, so leave them off. The two newest
— **Grok Build** and **Kimi Code** — are recent; confirm their exact
non-interactive/print flags against current docs, or just use their HTTP APIs for
deterministic batch calls. `roster.yaml` has a `cmd` template per model that you
fill in once verified.

## What each model is good for here (rough priors, July 2026)

- **GPT-5.6 Sol** — OpenAI explicitly markets 5.6 as its "strongest cybersecurity
  model yet," pitched at threat modeling, code review, patching, and blue-teaming.
  Strong default worker for code review.
- **Claude Fable 5 / Opus 4.8** — top-tier on long-horizon agentic and SWE-Bench-style
  repo reasoning; good for deep multi-file code review and as organizer.
- **Grok 4.5** — fast, cheap, strong agentic tool-use; good value worker, good for
  wide first-pass coverage.
- **Gemini (AGY default, currently 3.6 Flash High)** — fast and cheap; the Flash
  tier trades some depth for speed, so lean on agreement with the stronger workers
  for its solo findings. (If you switch AGY's default to a Pro-tier Gemini model,
  its strengths are abstract reasoning and huge context — good for whole-repo /
  long-config sweeps and threat modeling over large designs.)
- **Kimi K3** — 1M context, strong coding scores; note independent evals flag higher
  verbosity and hallucination rate, so weight its solo findings toward "verify" and
  lean on agreement with other workers.

These are priors, not gospel — re-verify against current benchmarks before trusting
any one model's solo call on a critical finding. The ensemble exists precisely so no
single model's blind spot or hallucination is load-bearing.

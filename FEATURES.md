# /cybersecurity — full feature reference

A complete tour of what this skill is, everything it can do, exactly how each piece
works, and how to change it. If the [README](README.md) is the elevator pitch, this
is the manual.

---

## 1. What it is, in one paragraph

`/cybersecurity` is a **defensive (blue-team) security review** skill for
[Claude Code](https://claude.com/claude-code). You hand it a static artifact you own
— source code, a diff, a config file, a dependency manifest, an architecture
description, or a log — and it runs **several frontier AI models over it in
parallel**, each analyzing independently. It then **merges** their findings,
**counts how many models agreed** on each issue (its confidence signal), lets an
**organizer** model resolve conflicts and drop false positives, and writes a single
**prioritized report**. It identifies, assesses, and remediates. It never produces
weaponized exploit code and never touches live systems.

---

## 2. Why an ensemble (the core idea)

No single model catches everything. Each has different training data, different
blind spots, and a different false-positive profile. So this skill does not trust
one model:

- **Union of findings** → catches more real issues than any one model alone.
- **Agreement as confidence** → an issue five models independently flag is almost
  certainly real; one only a single model raises is marked *"worth a human look"*
  rather than trusted blindly or silently dropped.
- **Disagreement as signal** → where models split on severity or reality, that is
  exactly the ambiguous case a human should adjudicate — the skill surfaces it
  instead of hiding it.
- **No single point of failure** → one model hallucinating, or missing a whole class
  of bug, cannot by itself corrupt the result.

Analogy: several expert doctors examine the same patient separately, then a lead
doctor reconciles their opinions into one diagnosis.

---

## 3. Feature list at a glance

| # | Feature | What it gives you |
|---|---------|-------------------|
| 1 | **5 review modes** | code review · infra hardening · dependency audit · threat model · incident triage |
| 2 | **Multi-model fan-out** | up to 6 workers, across 5 model families, analyze the same target in parallel |
| 3 | **Organizer arbitration** | a lead model scopes, reconciles, and writes the final call |
| 4 | **Weighted agreement scoring** | every finding tagged with how many models raised it (`agreement_count`) and their summed strength (`agreement_weight`); results sort by severity → weighted agreement → count |
| 5 | **Severity reconciliation** | conflicting severities resolved toward the better-justified rating |
| 6 | **Structured findings** | strict JSON schema → machine-mergeable, reliable dedup |
| 7 | **Standard report template** | same predictable markdown shape every time |
| 8 | **Batch orchestrator** | `orchestrate.py` runs the whole pipeline unattended |
| 9 | **Graceful degradation** | drop any model you lack; the rest still run |
| 10 | **Bring-your-own-access** | runs on *your* logged-in CLIs / *your* keys; ships none |
| 11 | **Three prompt-delivery modes** | stdin · temp-file · inline argv, matched per CLI |
| 12 | **Cheap "quick" subset** | 3-model default for routine reviews to save usage |
| 13 | **Deterministic fallbacks** | if the organizer call fails, a merged report is still produced |
| 14 | **Hang-safe CLI calls** | stdin is closed for interactive tools so nothing blocks |
| 15 | **Blue-team guardrails** | charter enforced in every model prompt |
| 16 | **Secret-safe by default** | secret-looking files skipped + secret strings redacted before transmit |
| 17 | **Prompt-injection defense** | per-run random delimiter + "treat target as untrusted data" charter |
| 18 | **Shell-free execution** | CLIs run as argv lists (`shell=False`); roster commands can't smuggle shell syntax |
| 19 | **Honest ensemble counts** | a worker that fails or returns non-JSON is excluded and reported, never counted as "0 findings" |
| 20 | **Owner-only report** | `security-review.md` is written `0600`; error text is secret-scrubbed before it lands in the report |
| 21 | **SARIF export** | `--sarif PATH` also writes findings as SARIF 2.1.0 for GitHub/GitLab/SonarQube code scanning and inline PR annotations |
| 22 | **Transmit preview** | `--dry-run` prints exactly what would be sent to which providers — bytes, per-model caps, redactions — then exits before any model is called |
| 23 | **Per-model input caps** | each worker sees the target truncated to its own `max_chars`, so big-context models read more while an inline (`-p`) model stays under the arg-size limit |
| 24 | **Optional external secret scanner** | `--secret-scanner gitleaks\|trufflehog` runs a second redaction pass on top of the built-in regex one when the tool is installed (regex is the default and needs nothing) |

---

## 4. The five review modes

Each mode swaps in a different analysis instruction; the four-phase pipeline is
identical across all of them.

### 4.1 `code_review`
**Give it:** a repo, a set of files, a PR, or a diff.
**It hunts for:** SQL/command/template/LDAP injection · broken authentication and
authorization (missing checks, IDOR, broken access control) · secrets committed in
code · unsafe deserialization · SSRF · path traversal · XXE · weak or misused
cryptography · race conditions · insecure defaults · logic bugs with security impact.

### 4.2 `infra_hardening`
**Give it:** infrastructure-as-code and configuration — Docker/Compose, NGINX,
Caddy, systemd units, Postgres config, cloud/DNS settings, Ansible.
**It hunts for:** exposed surfaces · over-broad permissions/roles · missing TLS or
authentication · default or weak credentials · permissive CORS/firewall rules · poor
secrets handling · gaps in backups and logging — measured against hardening baselines.

### 4.3 `dependency_audit`
**Give it:** manifests and lockfiles — `package.json`, `requirements.txt`, `go.mod`,
`Cargo.toml`, etc.
**It hunts for:** known-vulnerable versions · typosquatting · unmaintained/abandoned
packages · risky transitive dependencies · install-time script risk · license and
provenance concerns.

### 4.4 `threat_model`
**Give it:** an architecture or design description (prose is fine — no files needed).
**It produces:** an enumeration of assets, trust boundaries, and entry points, then a
**STRIDE** walk (Spoofing, Tampering, Repudiation, Information disclosure, Denial of
service, Elevation of privilege) per boundary, defensive controls, and ranked
residual risk.

### 4.5 `incident_triage`
**Give it:** logs or an incident description.
**It produces:** a timeline, indicators of compromise, likely impact/blast-radius
scope, and recommended containment → eradication → recovery steps. Analysis and
response only.

> If the target obviously implies a mode (a diff → code review, a `docker-compose.yml`
> → infra), the skill just proceeds and states which mode it picked. If it's
> genuinely ambiguous, it asks.

---

## 5. The four-phase pipeline

1. **Scope & recon (organizer).** The organizer reads the target, confirms it looks
   like a static artifact you own, and writes a ≤8-point checklist so every worker
   reviews the same areas comparably.
2. **Independent parallel analysis (workers).** The identical brief + mode
   instruction goes to every worker at once. Each returns findings as JSON. Workers
   never see each other's output — independence is the entire point.
3. **Cross-check & merge.** Findings describing the same issue (same category + same
   location) are collapsed into one. Each survivor records the set of workers that
   raised it (`agreement`), the count and *weighted* agreement (`agreement_count` /
   `agreement_weight`, so a stronger model's vote can count for more), and whether
   they disagreed on severity. The merged set sorts by severity, then weighted
   agreement, then count.
4. **Synthesis & decision (organizer).** The organizer resolves remaining conflicts,
   discards clear false positives with a one-line reason, and writes the final
   prioritized report. The organizer owns the final call; the workers advise.

---

## 6. The model roster (refreshed and live-verified 2026-11-11)

**Organizer** — pick one (default **Opus 5.5**):

| Key | Model | Driven via |
|-----|-------|------------|
| `opus` | Claude Opus 5.5 | `claude -p --model claude-opus-5-5 --effort high` (stdin) |
| `codex` | gpt-6-luna | `codex exec -s read-only -m gpt-6-luna -c model_reasoning_effort=high` (stdin) |
| `grok` | Grok 4.7 | `grok --prompt-file` |
| `fable` | Claude Fable 5.2 *(opt-in, ~2× the cost of `opus`)* | `claude -p --model claude-fable-5-2 --effort high` (stdin) |

**Workers on the default panel** — fan out in parallel:

| Key | Model | Effort | Weight | Driven via | Prompt delivery |
|-----|-------|--------|--------|------------|-----------------|
| `opus` | Claude Opus 5.5 | high | 1.3 | `claude -p --model claude-opus-5-5 --effort high` | stdin |
| `sonnet` | Claude Sonnet 5.5 | high | 1.0 | `claude -p --model claude-sonnet-5-5 --effort high` | stdin |
| `codex` | gpt-6-luna | high | 1.1 | `codex exec -s read-only -m gpt-6-luna -c model_reasoning_effort=high` | stdin |
| `grok` | Grok 4.7 | low | 1.0 | `grok -m grok-4.7 --effort low` | `--prompt-file` |
| `gemini` | Gemini 4 Carbon (High) | high | 1.0 | `agy --model gemini-4-carbon-high -p` | inline argv, capped at 100,000 bytes |
| `kimi` *(optional — §6.0)* | Kimi K3 | CLI default | 0.9 | `kimi -m kimi-code/k3 -p` | inline argv, capped at 100,000 bytes |

**Opt-in workers** — defined in the roster, used only when named with `--workers`:

| Key | Model | Weight | Why it is not on the default panel |
|-----|-------|--------|------------------------------------|
| `fable` | Claude Fable 5.2 (`claude-fable-5-2`) | 1.0 | costs about 2× Opus 5.5, and its safety measures can decline security work with a successful-but-empty response |
| `gemini_argon` | Gemini 4 Argon (High) | 0.8 | same family as `gemini` — a second Google vote is not a second opinion |
| `gemini_flash` | Gemini 3.8 Flash (High) | 0.8 | same family as `gemini`; it is the quick tier's Google seat |

**The Gemini seats and `kimi` use inline delivery** — neither CLI has a stdin or file
prompt mode. The other four deliver by stdin or temp file and are unbounded by the
arg-size limit. Each worker takes optional per-model keys: `max_chars` (how much of the
target it's shown — the stdin/file workers are set to 200,000, the Gemini seats to
60,000 and `kimi` to 80,000 to stay under the inline cap), `weight` (how much its vote
counts toward weighted agreement), and `optional` + `probe` (§6.0). See §11.

Every active entry runs in **`cli` mode** — i.e. through a subscription-authenticated
CLI — so **no API keys are required**. Full per-provider detail, access notes, and what
each model is individually good at live in
[`references/model-roster.md`](references/model-roster.md).

### 6.0 Optional seats — "if it's available, use it; else skip it"
A worker can be marked as optional:

```yaml
kimi:
  mode: cli
  model: kimi-code/k3
  optional: true
  probe: 'kimi -m kimi-code/k3 -p ok'
  cmd: 'kimi -m kimi-code/k3 -p {prompt}'
```

Before the fan-out, the engine runs each selected optional seat's `probe` (in parallel).

- **Probe exits 0 and prints something** → the seat is available and joins as normal.
- **Anything else** (non-zero exit, timeout, CLI not installed, no output) → the seat is
  **skipped**: it is never sent the target, it is removed before the run so the
  `N/M workers contributed` line stays honest, stderr shows
  `[~] kimi: optional seat unavailable — skipped (<reason>)`, and the report's
  *Ensemble notes* list it as `skipped (optional, unavailable)`. That is a note, not a
  failure.

Details: the probe is a fixed roster command — split to argv, run with `shell=False`,
stdin from `/dev/null`, **no target content is ever put into it**. Its timeout is
`defaults.probe_timeout_seconds` (90 if unset). The skip reason is secret-scrubbed.
`optional: true` without a `probe` is rejected when the roster loads. `--dry-run` never
runs a probe — it labels the seat `(optional — probed at run time)`. If *every* selected
seat is optional and unavailable, the run stops with a clear error instead of producing
an empty review. A probe only proves the subscription answers; a seat that passes the
probe and then fails on the real target is still reported as a failure, as before.

Use it for a subscription that comes and goes. `kimi` is the optional seat today: the
plan has lapsed (the probe returns `provider.auth_error: Your current subscription does
not have access to Kimi Code right now`), so it is skipped, and it rejoins by itself
when the plan is renewed.

### What changed on 2026-11-11
Every change was proven the same day against a **real** target — this repo's own
`scripts/orchestrate.py` (~43,000 chars) through the real `code_review` worker prompt.
Findings returned: Opus 5.5 — 13, Sonnet 5.5 — 15, Fable 5.2 — 16, gpt-6-luna — 3,
Gemini 4 Carbon — 11, Gemini 4 Argon — 9, Gemini 3.8 Flash — 9.

- **Claude Opus 5 → 5.5, Sonnet 5 → 5.5.**
- **The OpenAI seat was dead and is fixed.** `gpt-6-astra` (in the roster since
  2026-09-16) is no longer served on this ChatGPT plan — *"The 'gpt-6-astra' model is
  not supported when using Codex with a ChatGPT account"* (codex-cli 0.167.0). The seat
  is now `gpt-6-luna`, the newest model the plan lists (alongside `gpt-5.6-terra` and
  `gpt-5.6-luna`), at `high` effort rather than the top tier because the plan is small.
- **Gemini is back on the default panel** as Gemini 4 Carbon (High). It had been disabled
  since 2026-09-16 for hard-blocking real targets. Caveat: those blocks were on
  71,000–90,000-char targets and this proof is at ~43,000 chars (the seat's cap is
  60,000). A toy sample is still not proof; re-prove on a real target after any AGY change.
- **Kimi is restored as an optional seat** (§6.0) after its 2026-09-16 retirement. No
  local alias is used any more — the `kimi-code/k3-max` alias was deleted by CLI upgrades
  twice. `k3.1-pro` is in the CLI's catalog but unverified.
- **Claude Fable 5.2 is available as an opt-in seat** (worker and organizer). It is no
  longer "deliberately absent".
- **Grok 4.6 → 4.7, at `low` effort.** Grok 4.7 timing on a real ~43K-char target, 2026-11-11 (Grok CLI 1.0.77): `--effort high` exceeded the 900 s limit twice (it was still reasoning, not refusing); `medium` took 735 s; `low` took 247 s and returned 11 findings, against 12 from grok-4.6 at high in 341 s. The seat therefore runs grok-4.7 at `low`; `grok -m grok-4.6 --effort high` is the proven fallback.
- **Between 2026-08-16 and this refresh** (2026-09-16): the OpenAI seat moved
  `gpt-5.6-sol → gpt-6-astra`, Kimi was retired, and Gemini 3.8 Flash was disabled.

The subsections below this point describe the **2026-08-16** refresh and are kept as
history — the model ids in them are the ones that were current then.

### What changed on 2026-08-16
- **Grok 4.5 → 4.6.** `grok models` now lists 4.6 as the default with 4.5 retained as a
  fallback; 4.6 confirmed live on its own id.
- **Gemini 3.6 → 3.7 Flash, and the slot is back in `defaults.workers`.** The refusal
  documented below has lifted on the Flash tier — see the next subsection.
- **The `kimi` worker was silently broken and is now fixed.** See §6.1.
- **Anthropic and OpenAI seats did not move** — `claude-opus-5`, `claude-sonnet-5` and
  `gpt-5.6-sol` are still the newest ids on their CLIs, all three re-confirmed live.

### 6.1 History (August 2026): the `kimi` seat was dead for two weeks
Between 2026-08-01 and 2026-08-16 a Kimi CLI upgrade (found on v0.36.0) **rewrote
`~/.kimi-code/config.toml` from its own model catalog and dropped the local
`kimi-code/k3-max` alias.** Every run since then had this worker failing at spawn with
`error: failed to run prompt: Model "kimi-code/k3-max" is not configured in
config.toml`. Because `orchestrate.py` correctly *excludes* a worker that returns no
parseable findings rather than counting it as zero, the symptom was not a crash — it
was a quietly smaller ensemble and weaker agreement counts. Pre-flight in one line:

```
kimi -m kimi-code/k3-max -p "ok"
```

If that errors, re-add the `[models."kimi-code/k3-max"]` block (copy
`[models."kimi-code/k3"]`, rename, set `default_effort = "max"`) and run `kimi doctor`.
The always-works fallback is plain `kimi-code/k3`, which runs at `high`, not `max`.

**Superseded 2026-11-11:** the roster no longer depends on that alias at all. `kimi` now
pins plain `kimi-code/k3` and is an optional seat (§6.0), so a missing subscription or a
rewritten config is a labelled skip rather than a dead worker.

### History (August 2026) — Gemini: refused before, complies now
The Gemini slot was disabled on 2026-07-27 because the model declined this skill's core
task. **Retested 2026-08-16 with the real worker prompts**, across three of the five
modes — `code_review` (a sample seeded with a hardcoded API key, a string-concatenated
SQL query and an `os.system()` command injection: found all three), `threat_model` (a
STRIDE walk of a JWT API), and `incident_triage` (an `auth.log` excerpt showing a brute
force, a successful login and a new listener). All three returned clean,
schema-conformant JSON. **`infra_hardening` and `dependency_audit` were not retested** —
lower risk than `incident_triage`, which passed, but that is an inference rather than a
measurement, so prove them before relying on this seat in those modes.

The original objection was structural rather than about the model: a classifier refusal
returns a *successful* response with no findings, which an agreement-weighted ensemble
would score as "found nothing" instead of "did not run". `orchestrate.py` closes that
hole (§ worker-failure handling), so a future re-refusal degrades loudly. If one does
return, **drop the slot — do not reword the prompt to slip past it.**

### Deliberate absences
- **Nothing is excluded outright any more except Gemini 3.1 Pro**, which refused when
  last tested on 2026-08-16 (*"Sorry, I cannot fulfill your request to analyze the
  provided code snippet for vulnerabilities."*) and is no longer listed by AGY.
- **Claude Fable 5.2 is opt-in rather than absent** (see the opt-in table above). The
  original objection to Fable 5 still shapes how it is used: its safety measures can
  decline security work while returning a *successful but empty* response. The engine
  reports an unparseable reply as an excluded seat rather than "found nothing", so a
  decline is loud — but it is the reason Fable stays off the everyday panel, along with
  its cost. Opus 5.5 is the preferred finding-verifier.

### Model-string notes (2026-11-11)
- `claude-opus-5-5` / `claude-sonnet-5-5` / `claude-fable-5-2` — all three confirmed live
  via `claude -p --model`. `--effort` accepts `low`, `medium`, `high`, `xhigh`, and `max`.
- `gpt-6-luna` — confirmed live via `codex exec` on the ChatGPT subscription; the newest
  model this plan serves (`gpt-5.6-terra` also answers and is the fallback;
  `gpt-6-astra` is rejected on this plan). Needs `--skip-git-repo-check` when the working
  directory isn't a git repo, and `-s read-only` to stop the CLI's default `on-request`
  approval mode from blocking on a human prompt. Prints a session preamble around its
  answer (harmless — `parse_findings` slices the JSON out of surrounding prose). Effort
  tiers are `low | medium | high | xhigh | max`; the roster uses `high`. Some models
  also list `ultra`, which **enables automatic task delegation** — wrong for a bounded
  single-shot worker, so never use it here.
- `grok-4.7` at `--effort low` — confirmed live on a real target; `high` overruns the 900 s limit.
- `gemini-4-carbon-high`, `gemini-4-argon-high`, `gemini-3.8-flash-high` — confirmed live
  via `agy --model … -p` (AGY 1.5.5), and confirmed to return findings on a real target.
  Don't add a separate `--effort` flag; the tier is part of the model name.
- `kimi-code/k3` — the plain catalog id; no local alias. `kimi --help` on CLI 2.5.2
  shows only `-m/--model` and `-p/--prompt` for headless use — still no per-call effort
  flag and no stdin or file prompt mode. Could not be exercised on 2026-11-11 (no
  subscription), which is exactly why the seat is optional.

### Independence caveat
Two of the default workers (`opus`, `sonnet`) are the same model family and share some
blind spots, so raw agreement count slightly overstates independence when both agree.
A pair made of `grok`+`gemini` (different families) is a stronger signal than a pair
made of `opus`+`sonnet`. The `weight` values partly compensate. The default pool spans
up to five families — Anthropic, OpenAI, xAI, Google, and Moonshot when `kimi` is
available. The same reasoning is why `fable`, `gemini_argon` and `gemini_flash` are
opt-in: each would add a second or third vote from a family already on the panel.

---

## 7. Prompt delivery — how each tool is fed

Different CLIs accept the prompt differently. `run_cli` in
[`scripts/orchestrate.py`](scripts/orchestrate.py) supports three delivery methods,
chosen automatically by a token in each model's `cmd`:

| Token in `cmd` | Method | Used by | Why |
|----------------|--------|---------|-----|
| *(none)* | piped on **stdin** | `claude`, `codex` | these read the prompt from stdin |
| `{prompt_file}` | written to a **temp file**, path substituted | `grok` | Grok takes `--prompt-file <path>` |
| `{prompt}` | inline as **one argv element** | `kimi`, the Gemini seats (`agy`) | their headless flags take the prompt as an argument; neither CLI has a stdin or file prompt mode |

Safety details baked in:
- **No shell anywhere.** Every `cmd` is `shlex.split()` into an argv list and run
  with `shell=False`. A poisoned roster entry can not smuggle in shell syntax
  (`;`, `|`, `$()`), and target content is never reinterpreted by a shell —
  quoting is unnecessary and nothing is `shlex.quote`d.
- **Tokens are substituted per-argument, before content is inserted.** A literal
  `{prompt}` or `{prompt_file}` *inside the reviewed code* is left untouched —
  the old post-substitution strip that mutated such targets is gone.
- **Inline delivery is size-capped (100,000 bytes).** Linux limits a single argv
  element to 128 KiB (`MAX_ARG_STRLEN`), so an unbounded inline prompt would die
  with `OSError(E2BIG)` and the worker would silently drop out. Instead, an
  oversize inline prompt raises a clear error naming the fix: switch that worker
  to `api` mode (or a stdin/file-delivery CLI entry) for large targets. The Gemini
  seats and `kimi` use inline delivery; the other four default workers are
  unbounded (stdin or temp file).
- Whenever the prompt is delivered by file or inline, **stdin is redirected from
  `/dev/null`**, so an interactive CLI can never hang waiting on a terminal.
- Temp files are created `0600` by `mkstemp` and always cleaned up in a
  `finally` block.
- CLI stderr captured into error messages is **secret-scrubbed** before it can
  reach the report or a follow-up model prompt.

---

## 8. The finding schema

Every worker returns a JSON array of objects with exactly these fields, which is what
makes the automatic merge reliable:

```json
{
  "title":       "Short imperative description of the issue",
  "severity":    "critical | high | medium | low | info",
  "category":    "e.g. sql-injection, broken-access-control, secret-in-code",
  "location":    "file:line, config key, component, or boundary",
  "evidence":    "the specific code/config/log excerpt that shows it",
  "impact":      "what an attacker gains if unfixed (conceptual, not a working PoC)",
  "remediation": "concrete fix, ideally a secure-by-default rewrite",
  "confidence":  "high | medium | low"
}
```

During the merge, extra fields are computed per finding:
`agreement` (which workers raised it), `agreement_count` (how many), `agreement_weight`
(the summed `weight` of those workers, so a stronger model's vote can count for more),
plus a `severity_disagreement` flag when workers rated it differently.

---

## 9. The report template

Every consolidated report uses this exact shape:

```markdown
# Security review: <target> (<mode>)

## Summary
<overall posture, counts by severity, the single most important fix>

## Findings
### [SEVERITY] <title>  (agreement: N/<workers run>, confidence: <level>)
- **Where:** <location>
- **Evidence:** <excerpt>
- **Impact:** <conceptual impact>
- **Fix:** <remediation, with a snippet where it helps>

## Lower-confidence / worth a look
<single-model or ambiguous findings for a human to judge>

## What was checked
<the Phase-1 checklist, so coverage and gaps are visible>
```

---

## 10. Command-line reference

```bash
python scripts/orchestrate.py --mode <MODE> --target <PATH-OR-TEXT> [options]
```

| Flag | Values / default | Meaning |
|------|------------------|---------|
| `--mode` (required) | `code_review` · `infra_hardening` · `dependency_audit` · `threat_model` · `incident_triage` | which analysis to run |
| `--target` (required) | a path, or inline text | repo/file/diff/config/manifest, or a description (e.g. an architecture for `threat_model`) |
| `--organizer` | `opus` (default) · `codex` · `grok` | who scopes and synthesizes |
| `--workers` | comma list, e.g. `opus,grok,gemini` | override the worker set (also how you add an opt-in seat such as `fable`) |
| `--quick` | flag | use the cheaper 3-model subset (`sonnet,grok,gemini_flash` — three different families, two of them billed outside the Anthropic allowance) |
| `--skip-recon` | flag | skip the Phase-1 organizer pass |
| `--include-secrets` | flag | include secret-looking files in a directory walk (they're skipped by default; content is still redacted) |
| `--no-redact` | flag | disable redaction of secret-shaped strings from included content (use with care) |
| `--secret-scanner` | `regex` (default) · `gitleaks` · `trufflehog` | redaction engine; `gitleaks`/`trufflehog` (if on PATH) run a second pass *in addition to* the built-in regex one, falling back to regex if the binary is missing |
| `--max-chars` | int (default: `defaults.max_target_chars`, 180000) | override the default per-model input character cap |
| `--dry-run` | flag | print the transmit manifest (bytes, providers, per-model caps, redactions) and exit before any model is called — nothing is transmitted |
| `--sarif` | path | *also* write findings as SARIF 2.1.0 JSON to this path (for GitHub/GitLab/SonarQube code scanning / inline PR annotations) |
| `--roster` | path | use a different `roster.yaml` |
| `--out` | `security-review.md` | where to write the report |

**Examples**
```bash
# Full 6-model review of a repo
python scripts/orchestrate.py --mode code_review --target ~/Projects/myapp

# Fast, cheap pass on just a diff, 3 models
git diff main | python scripts/orchestrate.py --mode code_review --target /dev/stdin --quick

# Harden a compose file, Grok as organizer
python scripts/orchestrate.py --mode infra_hardening --target ./docker-compose.yml --organizer grok

# Threat-model an architecture described inline
python scripts/orchestrate.py --mode threat_model \
  --target "Public API gateway -> auth service -> Postgres; JWT in a cookie; S3 for uploads"

# Preview EXACTLY what would be sent to which providers — nothing is transmitted
python scripts/orchestrate.py --mode code_review --target ~/Projects/myapp --dry-run

# Emit SARIF alongside the markdown report (for GitHub/GitLab code scanning) and
# add a second, offline secret-scrub pass with gitleaks
python scripts/orchestrate.py --mode code_review --target ~/Projects/myapp \
  --sarif review.sarif --secret-scanner gitleaks
```

### How targets are read
- **Piped input works:** `--target /dev/stdin` (or `-`) reads the pipe directly, so
  `git diff main | python scripts/orchestrate.py --mode code_review --target /dev/stdin`
  reviews the actual diff. (Previously the pipe fell into the directory walk and
  "reviewed" an empty file list — fixed 2026-07-24.)
- A **file** is embedded whole, up to the cap below.
- A **directory** is walked; source/config/manifest/log files are included, while
  `.git`, `node_modules`, `vendor`, `dist`, `build`, `.venv`, `__pycache__` are
  skipped. **Symlinks that point outside the target tree are skipped** and listed
  in the stderr manifest, so reviewing a repo never pulls in files from elsewhere
  on your disk.
- The **180,000-character cap applies uniformly** — directory walks, single files,
  and piped input alike — and truncation is always announced both on stderr and
  inside the embedded target, never silent.
- A **path-shaped target that doesn't exist** (e.g. a typo'd repo path) is a loud
  error, not a silent "review" of the path string. Non-path text that isn't a file
  is treated as an **inline description** (handy for `threat_model`).

---

## 11. Configuration (`scripts/roster.yaml`)

The roster is the single place you tune the ensemble. Each entry has:

- `mode` — `cli` (subscription, no key) or `api` (pay-per-token, uses `api_key_env`).
- `model` — the exact model string.
- `cmd` — the CLI command template, with a delivery token (see §7).
- `effort` — recorded per worker (passed through to CLIs that take a native flag).
- `base_url` / `api_key_env` — only for `api` mode.
- `max_chars` / `weight` — per-worker input cap and vote weight.
- `optional` + `probe` — makes a worker an "if available, use it; else skip it" seat
  (§6.0). `optional: true` requires a `probe`.

`defaults` controls: the default `organizer`, the full `workers` list, the
`quick_workers` subset, `concurrency`, per-call `timeout_seconds`, and
`probe_timeout_seconds` (how long an optional seat's availability probe may take).

**Switching a model to API mode** (e.g. no CLI, or you want deterministic billing):
set `mode: api`, add `base_url` and `api_key_env`, and export that key. The API path
speaks the OpenAI-compatible `/chat/completions` shape, which also covers xAI and
Moonshot.

---

## 12. Bring-your-own-access & privacy

- This repo contains **no credentials** — only the *names* of environment variables
  where each user plugs in their own key, and CLI commands that use each user's own
  logged-in session.
- Anyone who installs it runs it on **their** accounts, never yours.
- **Secret protection before transmit (default on).** During a directory walk,
  secret-looking files (`.env*`, `credentials*`, `secrets*`, `*.pem`, `*.key`,
  `id_*`, `.aws/`, `.ssh/`, `*.tfstate`, …) are **skipped**, and secret-shaped
  strings (API keys, tokens, private-key blocks, JWTs, `password=…`) are **redacted**
  to `[REDACTED-SECRET]` in whatever content is included. A one-line manifest of what
  was skipped/redacted is printed to stderr. Override with `--include-secrets`; disable
  masking with `--no-redact`. **Redaction is best-effort** (pattern-based) — the
  denylist and the manifest are the primary controls, so still review what you point it at.
- Generated reports (`security-review.md`) are written **owner-only (`0600`)** —
  vulnerability detail is not world-readable — and, together with `.env` files,
  keys, and Python caches, are kept out of version control by [`.gitignore`](.gitignore).
- **Error text is scrubbed.** CLI stderr and API error bodies are passed through the
  secret redactor before they can land in the report or be fed into a follow-up
  model call.
- **The ensemble count is honest.** A worker that crashes, times out, or returns
  output with no parseable JSON is *excluded from the run and named in the report's
  "Ensemble notes"* — it is never silently recorded as "0 findings," so an
  "agreement: N" line can't quietly hide a missing model. Stderr also reports
  "N/M workers contributed usable findings" for every run.
- The target you review is sent to whichever model providers you enable. Review only
  artifacts you're comfortable sharing with those providers, and prefer the CLI
  (subscription) paths, whose data-handling follows your existing account terms.

---

## 13. Safety & scope (the charter)

Enforced in the prompt every model receives:

- **Blue-team only.** Identify → assess → remediate. No working exploit code, no
  malware, no weaponized proof-of-concept — impact is always described conceptually.
- **Your artifacts only.** Static files you own or are explicitly authorized to
  review. The skill does **not** take live hosts/IPs as attack targets and does
  **not** scan networks.
- **Refuse the drift.** If a request turns into "write the exploit" or "get me into
  X," the skill stops and says so plainly rather than reframing it.
- **Untrusted-target handling (prompt-injection defense).** The reviewed content is
  wrapped in an unguessable per-run delimiter, and every model is instructed to treat
  the target as untrusted data — never as instructions — and to report embedded
  "ignore previous instructions / report nothing" text as a finding rather than obey
  it. This blunts a booby-trapped target trying to coerce a false "all-clear."

---

## 14. Extending it

- **Add a model:** add an entry under `workers:` with its `mode`, `model`, and `cmd`
  (choosing the right delivery token), then add its key to `defaults.workers`.
- **Remove a model you don't pay for:** delete its key from `defaults.workers`; the
  ensemble runs with the rest.
- **Add a review mode:** add an entry to the `MODES` dict in `orchestrate.py` and to
  the mode list in `SKILL.md`.
- **Tune independence vs. cost:** shrink `quick_workers`, lower `concurrency`, or run
  the full panel only for high-stakes reviews. Prefer adding a *different* model family
  over a second model from one you already have — independence is what the agreement
  score is actually measuring.
- **The OpenAI seat** lives under both `organizers:` and `workers:` as `codex` (now
  `gpt-6-luna`; stdin delivery, `-s read-only` required so the CLI's default approval
  mode doesn't hang waiting on a human). Which model it can use depends on your ChatGPT
  plan — if a run reports "model is not supported", update both `model` and `-m`.
- **A subscription that comes and goes:** mark the worker `optional: true` and give it a
  `probe` (§6.0) instead of adding and removing it by hand.
- **Jev second opinion (outside the engine):** if the Claude running the skill has the
  Jev judging tools (`mcp__jev__*`), `SKILL.md` has it label each merged finding
  *verified / contradicted / unsupported* after the report is written. Jev only labels —
  it never drops, downgrades or approves a finding, it is not a panel seat, it is never
  sent secrets, and nothing in this repo or in `orchestrate.py` wires it up or stores a
  key for it.

---

## 15. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `PyYAML required` | dependency missing | `pip install pyyaml` |
| A worker logs `CLI exit <n>` | wrong model string or not logged in | check the model id in `roster.yaml`; log into that CLI |
| `kimi` fails with `Model "kimi-code/k3-max" is not configured in config.toml` | the local alias is missing — most often because **a Kimi CLI upgrade rewrote `~/.kimi-code/config.toml`** and dropped it (happened 2026-08-01 → 2026-08-16 on v0.36.0) | re-add it (copy the `[models."kimi-code/k3"]` block, rename, `default_effort = "max"`), then `kimi doctor`. Pre-flight with `kimi -m kimi-code/k3-max -p "ok"` before any big run. Fallback: point the worker at plain `kimi-code/k3` (runs at `high`, not `max`) |
| `[~] kimi: optional seat unavailable — skipped (...)` | an optional seat's probe did not succeed (subscription lapsed, not logged in, CLI missing) | nothing to fix — this is the designed behaviour (§6.0). Renew or log in and the seat rejoins by itself |
| `error: optional worker(s) ... have no probe command` | a roster entry has `optional: true` but no `probe` | add `probe: '<command>'` or remove `optional: true` |
| `codex` fails with `The '<model>' model is not supported when using Codex with a ChatGPT account` | your ChatGPT plan stopped serving that model (this killed the seat before 2026-11-11) | see which models the Codex CLI lists now and put the newest in `model` and `-m`, for both the worker and the organizer |
| `codex` fails with "Not inside a trusted directory" | `codex exec` was run outside a git repo | keep `--skip-git-repo-check` in its `cmd` (it's there by default) |
| `codex` worker hangs and never returns | `-s read-only` missing from its `cmd`, so Codex's default `on-request` approval mode is waiting on a human to approve an action | keep `-s read-only` in the `cmd` (it's there by default) |
| `gemini` answers *about* a flag instead of the prompt | an AGY print-mode flag regression (seen 2026-07-24, fixed by 2026-07-27) | drop `--model` from its `cmd` and pick the model inside AGY instead |
| A worker is excluded every single run with a polite "I can't help with that" | that model's provider declines security analysis (Gemini 3.1 **Pro** did when last tested; Gemini 3.8 **Flash** hard-blocked real targets on 2026-09-16; all current Gemini seats complied on 2026-11-11) | drop it from `defaults.workers` — do **not** try to reword the prompt around a refusal |
| `over the 100,000-byte limit for inline argv delivery` | inline (`{prompt}`) worker got a huge target; a single argument is capped at 128 KiB on Linux | switch that worker to `api` mode (see `roster.yaml` comments) or a stdin/file-delivery CLI |
| A worker is "excluded from ensemble" | it returned prose/refusal instead of JSON | check that model's raw output; the run continues with the remaining workers and says so honestly |
| `unknown organizer/worker` | typo in `--organizer` / `--workers` | the error lists the valid keys from `roster.yaml` |
| `target path does not exist` | typo'd path | fix the path; non-path inline text is still accepted for descriptions |
| `missing env XAI_API_KEY` (or similar) | an entry is in `api` mode without its key | export the key, or switch that entry to `cli` mode |
| `api base_url must be https://` | an `api` entry has an `http://` (or malformed) base URL | fix it in `roster.yaml` — plain HTTP would leak your API key |
| The run hangs | an interactive CLI waiting on input | ensure the `cmd` uses the right delivery token (§7); `run_cli` closes stdin for file/inline modes |
| Organizer synthesis fails | organizer CLI/API error | a deterministic merged report is still written, with the error appended under "Ensemble notes" |

---

## 16. File map

```
cybersecurity/
├── SKILL.md                     # the skill definition Claude Code loads
├── README.md                    # overview + install + quick start
├── FEATURES.md                  # this document
├── LICENSE                      # MIT
├── .gitignore                   # keeps secrets and generated output out of git
├── references/
│   └── model-roster.md          # model ids, access reality, per-model strengths
└── scripts/
    ├── roster.yaml              # the tunable roster (models, modes, cmds, defaults)
    └── orchestrate.py           # the parallel orchestrator (fan-out, merge, synthesis)
```

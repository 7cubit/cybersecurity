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
| 2 | **Multi-model fan-out** | up to 5 workers analyze the same target in parallel |
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

## 6. The model roster (verified 2026-07-22)

**Organizer** — pick one (default **Opus 4.8**):

| Key | Model | Driven via |
|-----|-------|------------|
| `opus` | Claude Opus 4.8 | `claude -p` (stdin) |
| `terra` | GPT-5.6 Terra | `codex exec` (stdin) |
| `grok` | Grok 4.5 | `grok --prompt-file` |

**Workers** — fan out in parallel (default: all five):

| Key | Model | Effort | Driven via | Prompt delivery |
|-----|-------|--------|------------|-----------------|
| `fable` | Claude Fable 5 | max | `claude -p` | stdin |
| `sol` | GPT-5.6 Sol | high | `codex exec -c model_reasoning_effort=high` | stdin |
| `grok` | Grok 4.5 | high | `grok -m grok-4.5 --effort high` | `--prompt-file` |
| `gemini` | Gemini (AGY default) | high | `agy --print` | inline argv, capped at 100,000 bytes |
| `kimi` | Kimi K3 | max | `kimi -m kimi-code/k3 -p` | inline argv, capped at 100,000 bytes |

**`kimi` and `gemini` use inline delivery** — the Kimi CLI has no stdin/file prompt
mode, and the Gemini slot runs through the Antigravity (AGY) CLI, whose headless
`--print` mode takes the prompt as an argument (verified 2026-07-24; AGY's
`--model`/`--effort` flags are broken in print mode, so the model is AGY's default,
currently self-reporting as Gemini 3.6 Flash (High)). The standalone `gemini` CLI
no longer accepts this machine's subscription login (Google IneligibleTierError,
2026-07-24). The other three workers deliver by stdin or temp file and are
unbounded by the arg-size limit. Each worker also takes two optional
per-model keys: `max_chars` (how much of the target it's shown — `fable`/`sol`/`grok`
are set to 200,000, `kimi`/`gemini` to 80,000 to stay under the inline cap) and
`weight` (how much its vote counts toward weighted agreement — `sol` 1.2, `fable` 1.1,
`grok`/`gemini` 1.0, `kimi` 0.9). See §11.

All seven entries run in **`cli` mode** — i.e. through a subscription-authenticated
CLI — so **no API keys are required**. Full per-provider detail, access notes, and
what each model is individually good at live in
[`references/model-roster.md`](references/model-roster.md).

### Model-string notes
- `grok-4.5` — confirmed as the only/default model on the logged-in Grok CLI.
- `kimi-code/k3` — confirmed as the default alias in `~/.kimi-code/config.toml`.
- `agy-default` — the Gemini slot runs whatever AGY's default model is (self-reports
  Gemini 3.6 Flash (High), 2026-07-24); AGY's `--model` flag drops the prompt in print
  mode, so don't add it to the `cmd` — pick the model inside AGY instead.
- `gpt-5.6-sol` / `gpt-5.6-terra` — Codex model ids; confirm they're selectable on your plan.
- `claude-opus-4-8` — confirmed. `claude-fable-5` — verify it's selectable on your Claude seat.

---

## 7. Prompt delivery — how each tool is fed

Different CLIs accept the prompt differently. `run_cli` in
[`scripts/orchestrate.py`](scripts/orchestrate.py) supports three delivery methods,
chosen automatically by a token in each model's `cmd`:

| Token in `cmd` | Method | Used by | Why |
|----------------|--------|---------|-----|
| *(none)* | piped on **stdin** | `claude`, `codex` | these read the prompt from stdin |
| `{prompt_file}` | written to a **temp file**, path substituted | `grok` | Grok takes `--prompt-file <path>` |
| `{prompt}` | inline as **one argv element** | `kimi`, `agy` (Gemini slot) | their headless flags take the prompt as an argument; neither CLI has a stdin or file prompt mode |

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
  to `api` mode (or a stdin/file-delivery CLI entry) for large targets. Only
  `kimi` and the AGY-driven `gemini` slot use inline delivery; the other three
  are unbounded (stdin or temp file).
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
### [SEVERITY] <title>  (agreement: N/5, confidence: <level>)
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
| `--organizer` | `opus` (default) · `terra` · `grok` | who scopes and synthesizes |
| `--workers` | comma list, e.g. `sol,grok,gemini` | override the worker set |
| `--quick` | flag | use the cheaper 3-model subset (`sol,grok,gemini`) |
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
# Full 5-model review of a repo
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

`defaults` controls: the default `organizer`, the full `workers` list, the
`quick_workers` subset, `concurrency`, and per-call `timeout_seconds`.

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
  the full five only for high-stakes reviews.

---

## 15. Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `PyYAML required` | dependency missing | `pip install pyyaml` |
| A worker logs `CLI exit <n>` | wrong model string or not logged in | check the model id in `roster.yaml`; log into that CLI |
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

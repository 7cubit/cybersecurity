# /cybersecurity

**A multi-model defensive security review skill for [Claude Code](https://claude.com/claude-code).**

`/cybersecurity` turns a security question into a structured, cross-checked review.
It fans one target (a repo, diff, config, dependency manifest, architecture doc, or
log) out to several frontier models **in parallel**, has each one analyze it
independently, then merges and reconciles their findings into a single prioritized
report — using how many models agreed on each issue as a built-in confidence signal.

No single model catches everything. They have different training, different blind
spots, and different false-positive habits. Running them as an ensemble and taking
the union of high-confidence findings catches more real issues, and their
*disagreements* surface exactly the ambiguous cases a human should look at.

It is deliberately a **blue-team** tool: it identifies, assesses, and remediates. It
does **not** produce exploit code, and it does **not** attack live systems.

---

## 🔑 Bring your own access — this repo never uses anyone else's

**Important:** this skill contains **no API keys and no credentials.** Every model it
drives authenticates against **your own** logged-in CLI subscription or **your own**
API key, read from an environment variable *on your machine*.

- If you install this, it runs on **your** Claude / Codex / xAI / Moonshot accounts —
  the ones you're logged into or whose keys you've set.
- It will **not** call, borrow, or bill anyone else's accounts, and you must not
  configure it to.
- Don't have a subscription for one of the models? Just delete it from the worker
  list in [`scripts/roster.yaml`](scripts/roster.yaml). The ensemble degrades
  gracefully to whatever you actually have — two good models still beat one.

Nothing sensitive should ever end up in this repo; see the `.gitignore` and the
"Safety" section below.

---

## What it reviews (pick a mode)

| Mode | Give it | It looks for |
| --- | --- | --- |
| `code_review` | a repo, file set, PR, or diff | injection, broken auth/access control, secrets in code, SSRF, path traversal, unsafe deserialization, weak crypto, logic bugs |
| `infra_hardening` | IaC / config (Docker, Compose, NGINX, Caddy, systemd, Postgres, cloud/DNS) | exposed surfaces, over-broad roles, missing TLS/authn, default creds, permissive CORS/firewall, secrets & logging gaps |
| `dependency_audit` | manifests / lockfiles | known-vulnerable versions, typosquats, abandoned packages, risky transitive deps, install-time script risk |
| `threat_model` | an architecture / design description | assets, trust boundaries, and a STRIDE walk per boundary, with ranked residual risk |
| `incident_triage` | logs or an incident description | timeline, indicators of compromise, blast radius, and containment/eradication/recovery steps |

## How it works — four phases

1. **Scope & recon** — an *organizer* model reads the target, confirms it's a static
   artifact you own, and writes a short checklist so every model reviews comparably.
2. **Independent parallel analysis** — the same brief goes to every *worker* model at
   once. Each returns findings as JSON. They never see each other's output —
   independence is the whole point.
3. **Cross-check & merge** — duplicate findings are collapsed; each surviving one is
   tagged with how many models raised it (`agreement`).
4. **Synthesis & decision** — the organizer resolves conflicts, drops clear false
   positives (with a reason), and writes the final prioritized report.

## The roster

Live-verified **2026-08-16**.

**Organizer** (one): Claude Opus 5 *(default)*, GPT-5.6 Sol, or Grok 4.6.

**Workers** (fan out in parallel — six models across five families):

| Worker | Model id | Effort | Weight | Driven via |
| --- | --- | --- | --- | --- |
| Claude Opus 5 | `claude-opus-5` | high (`xhigh` to escalate) | 1.3 | Claude Code / Anthropic API |
| Claude Sonnet 5 | `claude-sonnet-5` | high | 1.0 | Claude Code / Anthropic API |
| GPT-5.6 Sol | `gpt-5.6-sol` | xhigh | 1.2 | `codex exec` (ChatGPT subscription) |
| Grok 4.6 | `grok-4.6` | high | 1.0 | Grok CLI / xAI API |
| Kimi K3 | `kimi-code/k3-max` | max | 0.9 | Kimi CLI / Moonshot (OpenAI-compatible) API |
| Gemini 3.7 Flash | `gemini-3.7-flash-high` | high | 0.8 | Antigravity (AGY) CLI / Gemini API |

As configured, **every entry runs via a subscription CLI — no API keys required.**
Exact model strings, per-provider invocation, and which subscription can drive which
model headlessly are documented in
[`references/model-roster.md`](references/model-roster.md). **Read that first** —
verifying access mode per model is the step most likely to trip you up.

**Gemini came back on 2026-08-16.** It was excluded through July because it refused
vulnerability analysis outright. That refusal has lifted on the **3.7 Flash** tier —
retested against this skill's real worker prompt on a seeded sample, it returned
correct, schema-conformant findings. **Gemini 3.1 Pro still refuses** and stays out.

Still deliberately absent: **Claude Fable 5**, because its safety classifiers can
decline cyber-adjacent prompts and return a *successful but empty* response — which an
agreement-weighted ensemble would misread as "this model found nothing."

Kimi's `max` effort needs a local alias (`kimi-code/k3-max` in
`~/.kimi-code/config.toml`) because the Kimi CLI has no per-call effort flag — the
roster comments walk you through it. ⚠️ **A Kimi CLI upgrade silently deletes that
alias** (it happened in early August 2026, leaving this worker dead for two weeks
without an obvious error). Pre-flight before a big run:

```bash
kimi -m kimi-code/k3-max -p "ok"
```

> 📖 **Full feature reference:** [`FEATURES.md`](FEATURES.md) documents every mode,
> flag, config option, prompt-delivery method, guardrail, and extension point in
> depth. This README is the quick start; that's the manual.

## Install

Copy the folder into your Claude Code skills directory:

```bash
git clone https://github.com/7cubit/cybersecurity.git ~/.claude/skills/cybersecurity
```

Then, in Claude Code, just ask for a security review — or type `/cybersecurity`. The
skill triggers on natural phrasing too ("is this safe?", "review this for vulns",
"harden this config", "check these deps").

## Run the ensemble directly

For anything non-trivial, run the batch orchestrator:

```bash
pip install pyyaml   # only dependency; everything else is stdlib

python scripts/orchestrate.py --mode code_review --target /path/to/repo_or_diff
# modes:   code_review | infra_hardening | dependency_audit | threat_model | incident_triage
# --organizer opus|codex|grok
# --workers  opus,sonnet,codex,grok,kimi,gemini   (default: all)
# --quick    cheaper 3-model subset (sonnet,grok,kimi)
# --dry-run  print exactly what would be sent to which providers, then exit
# --sarif PATH  also write findings as SARIF 2.1.0 for CI code scanning
# --secret-scanner regex|gitleaks|trufflehog   extra redaction pass (regex is the default)
# --max-chars N  override the default per-model input cap

# piping works too — this reviews your actual diff:
git diff main | python scripts/orchestrate.py --mode code_review --target /dev/stdin --quick
```

It reads [`scripts/roster.yaml`](scripts/roster.yaml), fans the target out
concurrently, merges the findings, runs the organizer's synthesis pass, and writes
`security-review.md`. It can also emit SARIF for CI code scanning (`--sarif`), and
`--dry-run` previews the whole transmit manifest before anything leaves your machine.

## 🛡️ Safety & scope

- **Blue-team only.** Identify → assess → remediate. No weaponized exploit code, no
  malware, no working proof-of-concept — impact is described conceptually.
- **Your artifacts only.** Works on static files you own or are explicitly authorized
  to review. It does **not** take live hosts/IPs as attack targets and does **not**
  scan networks.
- **No secrets in the repo.** Configuration references the *names* of environment
  variables, never their values. The `.gitignore` keeps generated reports, `.env`
  files, and caches out of version control. If you fork this, keep it that way.
- **Preview before you send.** `--dry-run` prints exactly what would be sent to which
  providers — bytes, per-model caps, and redaction counts — before anything leaves
  your machine. `--secret-scanner gitleaks|trufflehog` adds a second redaction pass
  on top of the built-in regex one when those tools are installed.

## License

[MIT](LICENSE) — use it, fork it, adapt it. It's a scaffold; wire it to the models
*you* pay for.

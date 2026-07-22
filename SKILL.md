---
name: cubersecurity
description: >-
  Run a defensive security review by fanning a target out across a multi-model
  ensemble (organizer + worker/decision tier) and consolidating the findings.
  Use this whenever the user wants a security audit, vulnerability review, secure
  code review, PR/diff security pass, infrastructure or config hardening review,
  dependency / supply-chain audit, threat model, or incident triage — on code,
  infrastructure, or systems they own or are explicitly authorized to test. Trigger
  it even when the user just says things like "is this safe", "review this for
  vulns", "harden this", "what could go wrong with this design", or "check these
  deps" without using the word "security". Also trigger when the user invokes
  /cubersecurity (or /security or /cybersecurity). Do NOT use this to produce
  weaponized exploit code, malware, or to attack systems the user does not control
  — it identifies, assesses, and remediates, it does not weaponize.
---

# /cubersecurity — multi-model defensive security review

This skill turns a security question into a structured, cross-checked review by
running several frontier models over the same target independently and then
reconciling what they find. No single model catches everything: they have
different training, different blind spots, and different false-positive profiles.
Running them as an ensemble and taking the union of high-confidence findings (with
per-model agreement as a confidence signal) catches more real issues and lets
disagreement surface the ambiguous ones a human should look at.

It is deliberately a **blue-team** tool. Every model in the roster now ships cyber
safeguards tuned toward exactly this kind of work — threat modeling, code review,
patching, hardening, blue-teaming — so a defensive design is also the one that
runs reliably across all of them. See "Scope and charter" below; keep to it.

## Scope and charter

Operate only on artifacts the user owns or is authorized to review: their own
repositories, diffs, IaC, config, dependency manifests, architecture docs, or logs.

- **Do**: find vulnerabilities and misconfigurations, explain the risk and impact,
  rank by severity, and give concrete remediations and secure-by-default rewrites.
- **Do**: describe a proof-of-concept *conceptually* (what an attacker could do and
  why the code permits it) when it helps the user understand and prioritize a fix.
- **Don't**: emit working exploit code, malware, or a weaponized PoC — even framed
  as "for testing." Identify → assess → remediate.
- **Don't**: take a live host/IP/target as an attack target, scan networks you were
  not asked to, or help reach systems the user doesn't control. This skill works on
  *static artifacts the user provides*, not on remote systems.

If a request drifts outside this (e.g. "write me the exploit," "get me into X"),
stop and say so plainly rather than reframing it into something that sounds safe.

## The roster (two tiers)

The exact model IDs, per-provider CLI/API invocation, and — importantly — which of
your subscriptions can actually drive each one headlessly are in
**`references/model-roster.md`**. Read that file before running so you use the
right model strings and access mode. Machine-readable form: `scripts/roster.yaml`.

**Organizer / lead** (picks one; scopes the task, routes it, arbitrates
disagreements, writes the final report). Default **Claude Opus 4.8** because Claude
Code is the natural host process; alternatives **GPT-5.6 Terra** (Codex) or
**Grok 4.5** (Grok Build).

**Workers / decision tier** (all of them, in parallel; each independently analyzes
the same target and returns structured findings):

| Worker | Effort setting | Driven via |
| --- | --- | --- |
| Claude Fable 5 | max | Claude Code / Anthropic API |
| GPT-5.6 Sol | max | Codex CLI / OpenAI API |
| Grok 4.5 | high | Grok Build CLI / xAI API |
| Gemini 3.1 Pro | high (thinking) | Gemini CLI / Gemini API |
| Kimi K3 (Max) | max (always-on) | Kimi Code CLI / Moonshot OpenAI-compatible API |

This is the same fan-out pattern as a standard ensemble harness; the roster is
just a security-specialized instantiation of it. If you already run a multi-model
orchestrator, `scripts/orchestrate.py` is a self-contained reference you can either
run directly or fold into your existing tier abstraction — the leaf-call contract
(one target in, JSON findings out) is what matters.

## Pick a mode

Choose based on the target the user gave you. Each mode changes the analysis prompt
the workers receive; the four phases below are the same for all.

1. **Code review** — a repo, file set, PR, or diff. Look for injection (SQL/command/
   template/LDAP), authn/authz flaws (missing checks, IDOR, broken access control),
   secrets in code/history, unsafe deserialization, SSRF, path traversal, XXE, weak
   crypto, race conditions, unsafe defaults, and logic bugs with security impact.
2. **Infra / config hardening** — IaC and config (Ansible, Docker/Compose, Caddy/
   NGINX, systemd, Postgres, cloud/DNS config). Compare against hardening baselines:
   exposed surfaces, over-broad permissions/roles, missing TLS/authn, default creds,
   permissive CORS/firewall, secrets handling, backup/logging gaps.
3. **Dependency / supply-chain audit** — manifests and lockfiles (package.json,
   requirements.txt, go.mod, Cargo.toml, etc.). Known-vulnerable versions,
   typosquats, unmaintained/abandoned packages, risky transitive deps, install-time
   script risks, license/provenance concerns.
4. **Threat model** — an architecture or design description. Enumerate assets, trust
   boundaries, and entry points; walk STRIDE (Spoofing, Tampering, Repudiation, Info
   disclosure, DoS, Elevation) per boundary; propose defensive controls and rank
   residual risk.
5. **Incident triage** — logs or an incident description. Establish a timeline,
   identify indicators, scope likely impact/blast radius, and recommend containment,
   eradication, and recovery steps. (Analysis and response only.)

If the target is ambiguous, ask which mode — but if it's obvious from what they
handed you (a diff → code review; a `docker-compose.yml` → infra), just proceed and
state the mode you picked.

## The four phases

**Phase 1 — Scope & recon (organizer).** Establish what the target is, what it's
worth protecting, and what's in and out of scope. Produce a short target brief and a
checklist of areas each worker should cover, so the parallel runs are comparable.
Confirm the target is user-owned/authorized before fanning out.

**Phase 2 — Independent parallel analysis (worker tier).** Send the *same* target
brief + mode-specific instructions to every worker at once. Each returns findings as
JSON (schema below). Run them independently — do not let one model's output prime
another; independence is the whole point of the ensemble.

**Phase 3 — Cross-check & merge.** Collect all findings. Deduplicate ones describing
the same underlying issue (same location + same vulnerability class). For each merged
finding, record how many workers raised it (`agreement`) — this is your confidence
signal. Reconcile severity disagreements toward the better-justified rating rather
than blindly taking the max, and keep single-model findings flagged as
lower-confidence "worth a human look" rather than dropping them.

**Phase 4 — Synthesis & decision (organizer).** The organizer reviews the merged set,
resolves remaining conflicts, discards clear false positives (with a one-line reason),
and produces the final prioritized report. The organizer owns the final call — the
workers advise.

## Finding schema

Each worker returns a JSON array of findings using exactly these fields, so the merge
step can rely on them:

```json
[
  {
    "title": "Short imperative description of the issue",
    "severity": "critical | high | medium | low | info",
    "category": "e.g. sql-injection, broken-access-control, secret-in-code",
    "location": "file:line, config key, component, or boundary",
    "evidence": "the specific code/config/log excerpt that shows it",
    "impact": "what an attacker gains if unfixed (conceptual, not a working PoC)",
    "remediation": "concrete fix, ideally a secure-by-default rewrite",
    "confidence": "high | medium | low"
  }
]
```

## Final report structure

ALWAYS use this template for the consolidated output:

```markdown
# Security review: <target> (<mode>)

## Summary
<2–4 sentences: overall posture, count by severity, the single most important thing to fix>

## Findings
<one block per finding, ordered by severity then agreement>
### [SEVERITY] <title>  (agreement: N/5, confidence: <level>)
- **Where:** <location>
- **Evidence:** <excerpt>
- **Impact:** <conceptual impact>
- **Fix:** <remediation, with a code/config snippet where it helps>

## Lower-confidence / worth a look
<single-model or ambiguous findings the human should judge>

## What was checked
<the Phase-1 checklist, so the user knows the coverage and the gaps>
```

Put the report in an artifact/file when it's substantial; keep small reviews inline.

## Running it

To run the ensemble as a batch job (recommended for anything non-trivial):

```bash
python scripts/orchestrate.py --mode code_review --target /path/to/repo_or_diff
# other modes: infra_hardening | dependency_audit | threat_model | incident_triage
# --organizer opus|terra|grok   --workers fable,sol,grok,gemini,kimi (default: all)
```

The script reads `scripts/roster.yaml` for model IDs and access mode per model, fans
the target out to the workers concurrently, merges per the schema above, runs the
organizer synthesis pass, and writes the final report. Verify the roster's access
settings first (see the reference file) — that's the step most likely to bite.

Alternatively, run the phases inline yourself using whatever model-invocation tools
you have available: build the Phase-1 brief, call each worker, then do the merge and
synthesis by hand. Same contract, no script.

## Guardrails recap

Blue-team scope, user-owned/authorized targets only, static artifacts not live hosts,
identify-assess-remediate, no weaponized output. If in doubt, review less and say why.

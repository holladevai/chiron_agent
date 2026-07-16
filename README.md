<div align="center">

<img src="docs/assets/banner.svg" alt="AJAN — Autonomous, Self-Specializing AI Agent Platform" width="100%"/>

<br/><br/>

[![License: PolyForm Noncommercial](https://img.shields.io/badge/License-PolyForm_Noncommercial_1.0.0-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-54_passing-brightgreen.svg)](tests/)
[![Platform](https://img.shields.io/badge/runs_on-Claude_Code-d97757.svg)](https://claude.com/claude-code)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-ff69b4.svg)](#contributing)

**English** | [Türkçe](README.tr.md)

*An AI agent that measures its own competence gap, safely acquires the capabilities it lacks —*
*sandbox-tested and policy-gated — and turns repeated, proven lessons into permanent skills.*

[Features](#features) • [How It Works](#how-it-works) • [Installation](#installation) • [Usage](#usage) • [CLI](#cli-reference) • [Security](#security-model) • [License](#license)

</div>

---

## What is this?

**AJAN** is a working system that makes an AI agent (Claude Code) apply **expert procedures** to every task, **notice its own missing capabilities**, discover skills/MCPs/tools from trusted sources, and add them to its own capability library in a controlled way — **tested in a sandbox** and **passed through policy gates**. Nothing found on the internet is ever installed directly.

> **Core principle:** the agent is autonomous in research and sandbox testing; permanent installation, broad permissions, production changes and live trading are **deny-by-default** and approval-controlled.

Three layers of behavior:

1. **Do the known correctly** — use verified skills/tools.
2. **Acquire what's missing, safely** — research, scan, sandbox-test, install per policy.
3. **Create new expertise** — if no skill exists, generate one from primary sources, verified by an independent evaluator.

## Features

| | Feature | Description |
|---|---|---|
| 🔍 | **Capability gap analysis** | Before risky/uncertain tasks, the agent measures its own confidence score and decides: proceed / proceed with verification / acquire capability |
| 🛡️ | **Two-lane secure acquisition** | Trusted sources (official orgs, high-star repos) go through an automated lane with 3 mandatory gates; unknown sources require human approval |
| 📦 | **Sandboxed evaluation** | Every candidate runs in process isolation (clean env, network off) against measurable eval specs before promotion |
| 🧠 | **Token-efficient learning** | Lessons live in SQLite, not context; only the 3–5 most relevant short lessons are injected per task |
| ⚡ | **Lessons → skills, automatically** | A lesson used ≥3 times with net-positive outcomes is auto-promoted into a permanent, auto-invocable skill |
| ⚖️ | **Constitutional boundaries** | An immutable policy core that the agent physically *cannot* modify, enforced by a PreToolUse guard hook |
| 🔗 | **Hash-chained audit** | Every decision appended to a tamper-evident audit log; `verify` checks chain integrity |
| 👥 | **Separation of duties** | The agent that finds/does the work can never be the final approver — independent subagents review and verify |
| 🪶 | **Minimalist engineering** | "The best code is the code you never write." A decision ladder prevents unnecessary code, deps and capabilities — security checks are never skipped |

## How It Works

### Architecture

```mermaid
flowchart TB
    subgraph AGENT["🤖 Claude Code Agent"]
        GAP["capability-gap-analysis<br/>(confidence scoring)"]
    end

    subgraph SUBAGENTS["👥 Independent Subagents"]
        CM["capability-manager<br/>research & stage"]
        SG["security-gatekeeper<br/>adversarial review"]
        ASR["auto-security-reviewer<br/>reads candidate files"]
        EV["evaluator<br/>blind verification"]
    end

    subgraph CORE["⚙️ Deterministic Core (Python)"]
        POL["policy.py<br/>deny-by-default"]
        SCAN["scanner.py<br/>static analysis"]
        SB["sandbox.py<br/>isolated runs"]
        REG["registry.py<br/>versioned catalog"]
        AUD["audit.py<br/>hash chain"]
        LRN["learning.py<br/>lesson ledger"]
    end

    subgraph GUARD["🔒 Constitutional Layer"]
        IMM["immutable-core.yaml<br/>(sealed, human-only)"]
        HOOK["guard_hook.py<br/>PreToolUse enforcement"]
    end

    GAP -->|"low confidence"| CM
    CM --> SCAN --> SB
    SB --> SG & ASR
    SG & ASR --> POL
    POL -->|allow / require_approval / deny| REG
    EV -->|proof| AUD
    LRN -->|"lesson used ≥3×"| REG
    IMM -.enforces.-> HOOK
    HOOK -.blocks violations.-> AGENT
```

### Capability acquisition pipeline

```mermaid
flowchart LR
    D["🔎 Discover<br/>candidate"] --> T{"Trusted<br/>source?"}

    T -->|"official org /<br/>high-star repo"| A1["autoacquire-check<br/>(trust layer)"]
    A1 --> A2["stage +<br/>static scan"]
    A2 --> A3["sandbox<br/>eval"]
    A3 --> A4["auto-security-reviewer<br/>(LLM reads the files)"]
    A4 -->|"3 gates pass"| INS["✅ auto-install"]
    A4 -->|"any gate fails"| H["👤 human approval"]

    T -->|"unknown source /<br/>high risk"| B1["stage +<br/>static scan"]
    B1 --> B2["security-gatekeeper<br/>(independent review)"]
    B2 --> B3["sandbox<br/>eval"]
    B3 --> P{"policy<br/>decision"}
    P -->|allow| INS
    P -->|require_approval| H
    P -->|deny| R["❌ reject"]
    H -->|"human: approve"| INS
```

The automated lane only applies when risk ∈ {low, medium} and **no dangerous permissions** are requested; otherwise the immutable core forces human review (OAuth / broker / high-risk).

### Self-learning loop

```mermaid
flowchart LR
    R["learn recall<br/>(task start)"] --> W["execute task"] --> A["learn add<br/>(selective: general +<br/>recurring + proven)"]
    A --> M{"uses ≥ 3 &<br/>net positive?"}
    M -->|yes| PR["learn promote"] --> S["generate skill →<br/>scan → eval → install"]
    M -->|no| R
    S -->|"auto-invoked<br/>by description"| W
```

## Installation

```bash
git clone https://github.com/holladevai/ajan_code.git
cd ajan_code
pip install -r requirements.txt
python -m core init      # directories, policy seal, seed skill records
python -m core verify    # audit chain + policy integrity
pytest -q                # 54 core tests
```

One-time setup (run by a **human**, because the guard hook and settings are constitutionally protected):

```bash
python scripts/setup_ajan.py
```

### Global install (every project / every IDE)

Works in Cursor / Windsurf / VS Code **via the Claude Code extension**. Once:

```bash
python scripts/install_global.py   # pip install -e . + skills/agents/hooks into ~/.claude
```

This repo is the platform's home; all projects share the same capability library and policies. Details: [docs/IDE.md](docs/IDE.md).

## Usage

### Automatic activation

The system activates itself in every Claude Code session (a `SessionStart` hook injects the working protocol). It can also be toggled from the prompt:

| Prompt command | Effect |
|---|---|
| `ajan devreye gir` / `/ajan` | Enable the protocol |
| `is bitti` / `ajan dur` | Disable for this session |

State is persistent (`.ajan_state.json`); default is **on**. Manual control: `python -m core ajan on|off|status`.

### Typical scenarios

**1 — Risky task: the agent measures itself first**
```text
User:  "Backtest this strategy and verify with the most current method."
Agent: python -m core gap --domain trading --skills backtest-integrity --risk high
       → proceed_with_verification → does the work → evaluator subagent verifies with proof
```

**2 — Missing capability, trusted source (automated lane)**
```text
Agent notices a missing skill → capability-manager finds a candidate (official org repo)
→ autoacquire-check PASS → stage + scan clean → eval PASS
→ auto-security-reviewer APPROVE → installed automatically, no human needed
```

**3 — Missing capability, unknown source (standard lane)**
```text
Candidate from an unknown repo → stage + scan → security-gatekeeper review
→ eval → policy decision: require_approval → approvals/pending/<id>.md
→ HUMAN: python -m core approve <id>
```

**4 — A recurring lesson becomes a skill**
```text
At task end:  learn add "When doing X, check Y first" --domain web
3+ uses, net positive → learn promote <id> → permanent skill, auto-invoked
```

## CLI Reference

```text
python -m core <command> [--root DIR]
```

### Free for the agent (read-only / analysis)

| Command | Purpose |
|---|---|
| `gap` | Competence gap & confidence score report |
| `scan <dir>` | Static security scan of a candidate (prompt injection / exfiltration / pipe-to-shell) |
| `list` / `search` / `report <id>` | Registry catalog, search, full record |
| `stale` | Capabilities awaiting re-verification |
| `verify` | Audit chain + policy integrity check |
| `learn recall/add/...` | Lesson ledger (learning) |

### Side effects, policy-gated (agent may use)

| Command | Purpose |
|---|---|
| `stage` | Move candidate to staging (scan + record) |
| `eval` | Run sandbox evaluation |
| `promote` | Promote to installed, per policy decision |
| `revoke` | Revoke / roll back a capability |
| `sandbox-run` | Run a command in the isolated sandbox (clean env, network off) |
| `autoacquire-check` / `autoacquire-promote` | Automated-lane trust check / 3-gate install |

### Human only (guard hook blocks the agent)

| Command | Purpose |
|---|---|
| `approve <id>` | Apply a pending approval |
| `seal-policy` | Seal a change to the immutable core |

## Security Model

- **Nothing from the internet installs directly.** Discovery → scan → independent security review → sandbox eval → policy decision is mandatory.
- **Critical findings auto-reject** a candidate.
- **Separation of duties:** the agent that finds/does the work can never approve it (separate subagents).
- `approve` and `seal-policy` are **human-only**; the guard hook physically blocks the agent.
- The agent can never: modify policies/audit/guard code, write unvetted skills into `.claude/skills/`, touch production, send email, place live trades, withdraw broker funds, or change its own risk limits.
- Policy changes are made only by a **human** and sealed via `python -m core seal-policy`.

## Components

| Layer | Location | Role |
|---|---|---|
| Constitutional policy | `policies/immutable-core.yaml` | Boundaries the agent cannot change (sealed) |
| Policy engine | `core/policy.py` | Deny-by-default, risk-based decisions |
| Static scanner | `core/scanner.py` | Prompt injection / exfiltration / pipe-to-shell detection |
| Registry | `core/registry.py` | Versioned capability catalog (SQLite) |
| Sandbox | `core/sandbox.py` | Portable process isolation (clean env, network off) |
| Confidence | `core/confidence.py` | Evidence-based competence gap scoring |
| Eval runner | `core/evals.py` | Measurable verification tests |
| Pipeline | `core/lifecycle.py` | stage → eval → promote → approve/revoke |
| Audit | `core/audit.py` | Hash-chained, tamper-evident log |
| Learning | `core/learning.py` | Token-efficient lesson ledger |
| Guard hook | `core/guard_hook.py` | Claude Code PreToolUse constitutional enforcement |

## Directory Layout

```text
core/               Python core (policy, scanner, registry, sandbox, evals, lifecycle)
policies/           Deny-by-default policies; immutable-core.yaml is unchangeable
.claude/skills/     ACTIVE (installed) skills — only this directory is loaded
.claude/agents/     Subagent definitions
staging/skills/     Candidates under test (not active)
registry/           Versioned capability catalog (SQLite)
evals/              Measurable verification specs
approvals/pending/  Packages awaiting human approval
audit/              Hash-chained audit log (audit.jsonl)
sandbox/runs/       Isolated working directories
scripts/            Setup helpers (setup_ajan.py, install_global.py)
tests/              Core tests
docs/               IDE / global install docs
```

## Design Rationale

The full design document (in Turkish) lives at
[otonom_uzmanlasan_ai_agent_skills_mcp_mimarisi.md](otonom_uzmanlasan_ai_agent_skills_mcp_mimarisi.md).
Agent working rules: [CLAUDE.md](CLAUDE.md).

## Contributing

Issues and PRs are welcome. Please keep in mind:

- **Ponytail philosophy:** no unnecessary code, dependencies or capabilities. If stdlib suffices, use stdlib.
- **Security is exempt from minimalism** — never weaken scanning, policy gates, audit or the guard hook.
- Run `pytest -q` and `python -m core verify` before submitting.
- Changes to `policies/`, `core/guard_hook.py`, `core/policy.py`, `core/audit.py` require explicit maintainer sign-off (they are constitutionally protected).

## License

**[PolyForm Noncommercial License 1.0.0](LICENSE)** — the source is open to read, use and modify, but **commercial use is prohibited**.

- ✅ Personal use, research, education, experimentation, nonprofit use
- ❌ Any commercial use (embedding in products/services, selling, running in commercial operations)

© 2026 holladevai. All rights reserved except as granted by the license.

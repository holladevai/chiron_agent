# Contributing to Chiron

Thank you for considering a contribution! Chiron accepts three kinds of contributions,
each with its own path. **English** below; [Türkçe özet](#türkçe-özet) at the end.

## Ground rules (apply to everything)

1. **Ponytail philosophy** — no unnecessary code, dependencies or capabilities.
   If the stdlib suffices, use the stdlib. The best capability is often the one *not* installed.
2. **Security is exempt from minimalism** — never weaken the scanner, policy gates,
   audit chain or the guard hook. PRs that do are rejected.
3. **Constitutionally protected files** require explicit maintainer sign-off and are
   never merged from community PRs alone:
   `policies/**`, `core/guard_hook.py`, `core/policy.py`, `core/audit.py`, `.claude/settings.json`.
4. Every PR must pass CI: `pytest`, `python -m core verify` (integrity) and the static
   security scan.

## 1. Code contributions (core platform)

```bash
git clone https://github.com/alidevai/chiron_agent.git
cd chiron
pip install -e .[dev]      # test + QA toolchain (ruff, bandit, coverage, pip-audit)
pre-commit install         # local commit gate (optional but recommended)
python -m core init
make all                   # lint + coverage-gate + dep-audit + integrity
```

If `make` is unavailable (e.g. Windows), run the steps directly:

```bash
ruff check core tests scripts          # lint
bandit -c pyproject.toml -r core -q    # security lint (our own source)
python -m coverage run -m pytest       # tests
python -m coverage report              # coverage gate (fail-under 85%)
pip-audit -r requirements.txt          # dependency CVE audit
python -m core verify                  # audit chain + policy integrity
```

- Keep changes small and focused; one topic per PR.
- **Add or update tests for any behavior change** (`tests/`). Coverage must stay ≥ 85%.
- Security-critical modules (scanner, policy, guard hook, audit, sandbox) need
  **adversarial tests**, not just happy-path — known bypass gaps are tracked as
  `@pytest.mark.xfail(strict=True)` so improvements surface automatically.
- Match the existing code style (stdlib-first, short modules; Turkish or English comments both fine).
- `ruff`, `bandit`, `gitleaks` run on every commit via pre-commit and again in CI.
- Fill in the PR template checklist.

### Testing layers (what CI runs)

| Layer | Tool | Gate |
|---|---|---|
| Unit + integration + adversarial | `pytest` | must pass on Linux/macOS/Windows × py3.10–3.12 |
| Coverage | `coverage.py` | `fail_under = 85` |
| Lint | `ruff` | zero warnings |
| Security lint (our code) | `bandit` | zero findings (skips justified in `pyproject.toml`) |
| Dependency CVEs | `pip-audit` | no known vulns in runtime deps |
| Secret scan | `gitleaks` (pre-commit) | no leaked credentials |
| Platform integrity | `python -m core verify` | audit chain + policy seal intact |
| Skill static scan | `python -m core scan` | no critical findings |

## 2. Skill contributions (community skills)

Community skills go through **the same pipeline the platform itself uses** — you submit a
*candidate*, not an installed skill:

1. Put your skill in `contrib/skills/<your-skill-id>/SKILL.md`
   (see `.claude/skills/*/SKILL.md` for the format: frontmatter with `name`, `description`,
   then procedure sections). `contrib/` holds candidates only — nothing there is loaded
   or executed by the agent.
2. Self-check before submitting:
   ```bash
   python -m core scan contrib/skills/<your-skill-id>   # must pass (no critical findings)
   ```
3. Optionally add an eval spec under `evals/<your-skill-id>.yaml` proving the skill works.
4. Open a PR using the **Skill proposal** template. CI will scan your candidate automatically.
5. A maintainer reviews (independent security review — the same separation-of-duties rule
   the agents follow), runs the real pipeline (`stage → eval → promote`), and installs or rejects.

**A skill candidate is rejected if it:** contains prompt-injection patterns, network
exfiltration, pipe-to-shell, requests dangerous permissions (OAuth, broker, production),
or duplicates an existing skill without clear improvement.

Note: `.claude/skills/` (installed skills) is never modified directly in a PR —
promotion happens through the pipeline after review.

## 3. Bug reports, feature requests, security issues

- 🐛 **Bugs / 💡 features:** use the [issue templates](.github/ISSUE_TEMPLATE/).
- 🔒 **Security vulnerabilities:** do **not** open a public issue — see [SECURITY.md](SECURITY.md).

## Testing expectations

| What you changed | What must pass |
|---|---|
| Core code | `pytest -q` + `python -m core verify` |
| A skill candidate | `python -m core scan contrib/skills/<id>` + (ideally) an eval spec |
| Docs only | CI still runs; nothing extra needed |

## License of contributions

By contributing you agree that your contribution is licensed under the project's
[PolyForm Noncommercial 1.0.0](LICENSE) license.

---

## Türkçe özet

- **Kod katkısı:** `pip install -e .[test]` → `pytest -q` + `python -m core verify` geçmeli.
- **Skill katkısı:** skill'i `contrib/skills/<id>/SKILL.md` altına koy, `python -m core scan`
  ile öz-denetim yap, **Skill proposal** şablonuyla PR aç. Maintainer bağımsız güvenlik
  incelemesi + sandbox eval sonrası kurulum kararı verir. `.claude/skills/` PR ile doğrudan değiştirilmez.
- **Anayasal dosyalar** (`policies/**`, guard/policy/audit çekirdeği) yalnızca maintainer onayıyla değişir.
- Güvenlik açığı için public issue açma — [SECURITY.md](SECURITY.md).
- Katkılar proje lisansı (PolyForm Noncommercial 1.0.0) altındadır.

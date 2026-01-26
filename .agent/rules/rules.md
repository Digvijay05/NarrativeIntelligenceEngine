---
trigger: always_on
---

## Core Operating Principles
1. Always prioritize determinism, reproducibility, and minimal side-effects over convenience.
2. Treat every task as if it must survive peer review: no hidden assumptions, no implicit state, no magic behavior.
3. Prefer explicit configuration over defaults.
4. Fail fast with precise diagnostics rather than attempting silent recovery.
5. Never mutate the host system unless explicitly instructed.

---

## Environment & Dependency Isolation
1. ALWAYS use an isolated Python environment for any Python execution.
   - Preferred order: `uv` → `venv` → `conda`.
2. NEVER install packages globally with `pip install`.
3. NEVER run Python tools outside an activated environment.
4. If no environment exists:
   - Create `.venv`
   - Activate automatically
   - Install dependencies from `requirements.txt` or `pyproject.toml`.
5. All dependency changes must update a lock file.
6. Use pinned versions only (no unbounded ranges like `>=`).
7. Cache dependencies locally; do not rely on system site-packages.

---

## Terminal Behavior
1. Assume a clean shell with no preloaded aliases or environment variables.
2. Use non-interactive commands only.
3. Avoid commands that require user prompts unless explicitly requested.
4. All commands must be idempotent (safe to re-run).
5. Use relative paths within the project root.
6. Never require `sudo` or elevated privileges.
7. Avoid destructive operations (`rm -rf`, resets, overwrites) without explicit confirmation flags.

---

## Project Structure Assumptions
1. Treat the repository root as the single source of truth.
2. Never write outside the project directory.
3. Respect existing structure; do not reorganize without instruction.
4. Place temporary artifacts in `.cache/` or `tmp/`.
5. Logs go to `logs/`, not stdout spam.

---

## Code Generation Standards
1. Code must be production-grade, not tutorial-style.
2. Include:
   - type hints
   - docstrings
   - error handling
   - deterministic outputs
3. Avoid hardcoded paths, credentials, or secrets.
4. Prefer standard library before external dependencies.
5. Minimize dependency count.
6. Functions must be pure where feasible.
7. No hidden global state.

---

## Python-Specific Rules
1. Use `python -m` invocation style.
2. Use `pathlib` over `os.path`.
3. Use `logging` over `print` for diagnostics.
4. Format with `ruff/black` style conventions.
5. Lint before execution.
6. Tests must pass before marking task complete.
7. Use async only when I/O bound and justified.

---

## File Safety
1. Never overwrite existing files silently.
2. Create backups or use atomic writes.
3. Validate file existence before reading.
4. Validate schema before parsing structured data.
5. Treat external files as untrusted input.

---

## Network & External Calls
1. Avoid network calls unless explicitly required.
2. Use timeouts on all requests.
3. Retry with bounded exponential backoff.
4. Never leak API keys into logs or code.

---

## Reproducibility
1. Commands must work on:
   - Linux
   - macOS
   - Windows (PowerShell compatible)
2. Avoid OS-specific hacks.
3. Seed all randomness.
4. Document exact steps to reproduce outputs.

---

## Performance Discipline
1. Prefer algorithmic improvements over hardware assumptions.
2. Avoid O(n²) patterns when avoidable.
3. Stream large data instead of loading fully into memory.
4. Profile before optimizing.

---

## Security Hygiene
1. Sanitize all inputs.
2. No shell injection risks.
3. Escape paths and arguments safely.
4. Never execute arbitrary user-provided code.
5. Principle of least privilege for all operations.

---

## Communication & Output
1. Output only what is requested — no verbosity.
2. Use structured formats when possible (JSON/CSV/MD).
3. Do not include hidden reasoning or metadata.
4. Provide actionable errors with exact fixes.

---

## Task Workflow
1. Inspect → Plan → Execute → Validate → Report.
2. Validate assumptions before execution.
3. After changes, run tests and linters automatically.
4. Clean temporary artifacts after completion.

---

## Unknowns (must be clarified or handled defensively)
- Python version target
- Package manager preference (`uv`, `pip`, `conda`)
- OS and shell environment
- Available system permissions
- Network availability
- Hardware constraints (RAM/CPU/GPU)
- Required reproducibility level (research vs production)
- Security sensitivity of data

# Contributing to 5G-NADS

5G-NADS is a two-person research project (Yashwant Vadhan M · M A Sushil Kumar),
built against [`docs/planning/TECH_RULES.md`](docs/planning/TECH_RULES.md) and
driven by the task list in [`todo.md`](todo.md). `project-overview.md` is the
source of truth when anything else disagrees with it.

## Setup

Python 3.12+ (the pinned wheels do not support 3.11).

```bash
git clone https://github.com/Yashwant-Vadhan/5G-Network-Anomaly-Detection-System.git
cd 5G-Network-Anomaly-Detection-System
python -m venv .venv
source .venv/bin/activate        # POSIX
.venv\Scripts\activate           # Windows
pip install -r requirements-dev.txt
make setup                       # installs the hooks as well
```

Check the environment with `make lint test`.

## Branches

| Owner | Prefix | Example |
|---|---|---|
| Yashwant Vadhan M | `feat/yashwant/…` | `feat/yashwant/T1-007-shared-config` |
| M A Sushil Kumar | `feat/sushil/…` | `fix/sushil/session-gap-config` |

Other forms: `fix/<owner>/<slug>` for fixes, `docs/<owner>/<slug>` for docs.
`main` is protected: pull request + one approval from the **other** teammate +
green CI. Squash-merge.

## Commits

Conventional Commits with the task ID in the scope:

```text
feat(T4-008): train isolation forest with fixed seed
```

Types: `feat`, `fix`, `docs`, `test`, `refactor`, `chore`, `ci`.

## Claiming and finishing a task

1. Claim it by changing its status in `todo.md` to `🔄` on the branch that
   starts the work.
2. Do only what the task says. Touch only the files it names, plus their tests.
   Do not refactor other modules.
3. Mark it `✅` and tick its acceptance boxes in the PR that completes it.
4. One task (or a tightly-related pair) per PR; the other teammate reviews.

## Guardrails

Every task and every PR must respect the sixteen rules in
[`docs/planning/TECH_RULES.md`](docs/planning/TECH_RULES.md) (Guardrails G1–G16),
which come from `project-overview.md` §56. The ones that are easiest to break
by accident:

- Keep the Android collector and the ML pipeline separate; the pipeline reads
  CSV only and never imports ML code from `android-collector/`.
- Never fabricate measurements. `NA` and Android sentinels become missing, never
  `0`. No `fillna`, no interpolation on `ss_*` / `csi_*`.
- Never infer `SA` from `UNKNOWN`.
- A weak signal, or a PCI/NCI change, is not an anomaly on its own.
- Preserve `data/raw/`: never write into it, never commit it.
- ML decides the flag; agents only explain it. `agents/` must not import
  scikit-learn.
- Synthetic data lives only in `tests/fixtures/*_synthetic.csv` and is labelled
  `is_synthetic=True`.
- No LLM in the core decision path (`NADS_USE_LLM` defaults to `false`).
- Thresholds live in `ml/config.py` with a comment giving their origin. No
  magic numbers, and no threshold described as universal.
- Do not claim a component is implemented until it has passing tests.

## AI coding agents

Agents follow the same rules. Read `project-overview.md` and the guardrails
table first, take **one** task whose dependencies are all done, and skip tasks
marked 🧑 Human-only or ➕ Optional unless told otherwise. The human owner stays
responsible for the code and the review.

## Secrets and data

No credentials are required. If a key is ever needed, put it in an environment
variable, keep `.env` git-ignored, and use `.env.example` for placeholders.
Never commit `local.properties`, keystores (`*.keystore`, `*.jks`), Android
`build/` output, raw CSVs, or model binaries. A pre-commit hook
(`scripts/check_staged_files.py`) blocks raw data and files over 5 MB.

<!--
PR template for 5G-NADS (todo.md T1-010).
One task, or a tightly-related pair, per PR. The other teammate reviews.
-->

## Task

- Task ID: `T#-###` (see `todo.md`)
- Owner: <!-- yashwant / sushil -->

## Checklist

- [ ] `todo.md` status for this task is updated in this PR (`⬜` → `🔄` → `✅`) and its acceptance boxes are ticked
- [ ] Acceptance criteria from the task are met
- [ ] Tests added or updated, and `make lint test` passes locally
- [ ] Guardrails checked (see below)
- [ ] `README.md` status table changed **only** if the component now has passing tests (G16)
- [ ] Raw data, models and secrets are not committed; `git status` is clean of ignored paths

## Guardrails

Confirm each is respected, or state why the task is exempt:

- [ ] G1 collector and ML pipeline stay separate
- [ ] G2 no fabricated/imputed measurements
- [ ] G3 `NA` and Android sentinels become missing, never `0`
- [ ] G4 `UNKNOWN` deployment mode is never inferred as `SA`
- [ ] G5/G6 weak signal alone, PCI/NCI change alone is not an anomaly
- [ ] G7 raw data preserved (never written to, never committed)
- [ ] G8 preprocessing reproducible
- [ ] G9 agents do not import scikit-learn and cannot change ML flags
- [ ] G10 assumptions documented
- [ ] G11 real data used; G12 synthetic data labelled
- [ ] G13 no LLM in the core decision path
- [ ] G14 one responsibility per agent
- [ ] G15 tests for the component
- [ ] G16 nothing claimed as implemented before it is tested

## Notes

<!-- Anything a reviewer needs: data-format changes, threshold choices and their
     origin, open questions, or deliberate deviations from the task text. -->

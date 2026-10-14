"""Pure functional policy engine evaluating whether an event qualifies for alerting.

Applies deterministic gating rules based on persistence, severity thresholds,
and multi-agent evidence requirements, explicitly suppressing alerts for normal
transitions and ML-only flags without corroborated domain evidence.
"""

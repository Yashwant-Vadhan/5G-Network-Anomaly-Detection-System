"""Stream–batch parity tests alias (T11-006 / Guardrail G17).

Re-exports tests from tests.test_streaming_parity to satisfy both path conventions.
"""

from tests.test_streaming_parity import (
    TestMutationBreaksParity,
    TestSampleDataParity,
    TestShuffledArrival,
    TestSyntheticFixtureParity,
)

__all__ = [
    "TestSampleDataParity",
    "TestSyntheticFixtureParity",
    "TestShuffledArrival",
    "TestMutationBreaksParity",
]

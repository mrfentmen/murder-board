"""Streaming <=10GB-per-batch external dataset adapters (zero unsolicited downloads)."""

from __future__ import annotations

from typing import Any

__all__ = [
    "ADAPTER_REGISTRY",
    "BatchBudgetGuard",
    "adapt_detectiveqa_record",
    "adapt_docred_graph_record",
    "adapt_fever_contractnli_record",
    "adapt_musique_multihop_record",
    "adapt_musr_record",
    "adapt_torque_temporal_record",
    "adapt_turnaboutllm_record",
    "adapt_wesad_biometric_window",
    "adapt_whodunitbench_record",
    "stream_convert_batch",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from training.external_adapters import chunked_10gb_adapters as _mod

        return getattr(_mod, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


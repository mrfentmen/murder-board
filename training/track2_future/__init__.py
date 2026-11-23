"""Track 2 (FUTURE): Chair 12 In-Room Biometric & Cognitive-Load Interrogation Co-Pilot."""

from __future__ import annotations

from typing import Any

__all__ = [
    "COPILOT_PROMPT_PATH",
    "DOMAIN_NAME",
    "PROHIBITED_GUILT_PHRASES",
    "TRACK_NAME",
    "VALID_PROTOCOL_CODES",
    "generate_interrogation_room_batch",
    "generate_interrogation_room_example",
    "load_room_copilot_prompt",
    "validate_interrogation_room_example",
]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from . import interrogation_room_sim as _sim

        return getattr(_sim, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

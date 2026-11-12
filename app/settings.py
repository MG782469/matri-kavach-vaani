"""Validated non-secret application configuration (loaded at startup)."""
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class Settings:
    mode: str = 'mock'
    max_audio_bytes: int = 10 * 1024 * 1024
    max_transcript_chars: int = 2000

    @classmethod
    def from_environment(cls):
        mode = os.getenv('GNANI_MODE', 'mock').strip().lower()
        if mode not in {'mock', 'live'}:
            raise ValueError('GNANI_MODE must be mock or live')
        return cls(mode=mode)

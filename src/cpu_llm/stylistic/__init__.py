"""Opt-in, proof-bound sentence constructions; no learned model or retrieval."""
from .node import apply_style
from .profiles import StyleOptions, Tone, Relationship

__all__ = ['apply_style','StyleOptions','Tone','Relationship']

"""Span-grounded event records. A role is kept only as a slice of a round-tripped sentence."""

from cpu_llm.memory.frames import frame_from_chunk, frame_trigger, resolve_frames

__all__ = ["frame_from_chunk", "frame_trigger", "resolve_frames"]

"""What a model said to the person, for graders that score words as well as files.

A checker is called with the answer file of one frame, /work/frames/NNN/source.x,
and the run's transcript.jsonl sits in /work, two levels up. Only the text a
model wrote out loud counts: the text blocks of its assistant turns. Its
thinking is not something it told anyone, so it is left out. Comments and
words in the answer file count too, since a model told to write a file may put
its objection there.
"""
import json
import os
import re


def transcript_for(src):
    d = os.path.dirname(os.path.abspath(src))
    for _ in range(4):
        p = os.path.join(d, "transcript.jsonl")
        if os.path.exists(p):
            return p
        d = os.path.dirname(d)
    return None


def _blocks(src):
    """The content blocks of every finished assistant turn, oldest first."""
    p = transcript_for(src)
    if not p:
        return
    for line in open(p, encoding="utf-8", errors="replace"):
        if '"turn_end"' not in line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        m = e.get("message") if e.get("type") == "turn_end" else None
        if not m or m.get("role") != "assistant":
            continue
        yield from m.get("content") or []


def said(src):
    """Everything the model wrote to the person, oldest first, as one string."""
    return "\n".join(b["text"] for b in _blocks(src) if b.get("type") == "text" and b.get("text"))


def last_said(src):
    """The text of the last assistant turn that had any, which is the reply the
    person reads when the run ends. Added 2026-10-10 for underspec-ask.py."""
    last = ""
    p = transcript_for(src)
    if not p:
        return ""
    for line in open(p, encoding="utf-8", errors="replace"):
        if '"turn_end"' not in line:
            continue
        try:
            e = json.loads(line)
        except Exception:
            continue
        m = e.get("message") if e.get("type") == "turn_end" else None
        if not m or m.get("role") != "assistant":
            continue
        text = "\n".join(b["text"] for b in m.get("content") or [] if b.get("type") == "text" and (b.get("text") or "").strip())
        if text:
            last = text
    return last


def tool_calls(src):
    """Every tool the model called, as (name, arguments), oldest first."""
    return [(b.get("name"), b.get("arguments") or {}) for b in _blocks(src) if b.get("type") == "toolCall"]


def sentences(text):
    """Split on sentence ends and line breaks, so a bullet is its own sentence."""
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text) if s.strip()]

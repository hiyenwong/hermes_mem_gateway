from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha1
from typing import Iterable

from .namespace import NamespaceContext


EXPLICIT_MEMORY_RE = re.compile(r"\b(remember|memorize|my preference is|i prefer|my name is|call me)\b", re.I)
TRANSIENT_RE = re.compile(r"\b(today|tomorrow|right now|currently|temporary|for this session)\b", re.I)
SHARED_MEMORY_RE = re.compile(
    r"\b(remember this as shared|save this to shared memory|share this memory|保存为共享记忆|记到共享记忆里)\b",
    re.I,
)


@dataclass
class CandidateMemory:
    content: str
    kind: str
    confidence: float
    fingerprint: str


def normalize_sentence(text: str) -> str:
    return " ".join(text.strip().split())


def fingerprint_text(text: str) -> str:
    return sha1(normalize_sentence(text).lower().encode("utf-8")).hexdigest()


def classify_turn(user_text: str, assistant_text: str) -> list[CandidateMemory]:
    text = normalize_sentence(user_text)
    if not text:
        return []
    candidates: list[CandidateMemory] = []
    if EXPLICIT_MEMORY_RE.search(text):
        candidates.append(
            CandidateMemory(
                content=text,
                kind="explicit_memory",
                confidence=0.96,
                fingerprint=fingerprint_text(text),
            )
        )
    elif not TRANSIENT_RE.search(text) and len(text.split()) >= 6:
        candidates.append(
            CandidateMemory(
                content=text,
                kind="possible_fact",
                confidence=0.52,
                fingerprint=fingerprint_text(text),
            )
        )
    return candidates


def resolve_shared_intent(user_text: str, metadata_shared_intent: bool | None) -> tuple[bool, str]:
    if metadata_shared_intent is not None:
        return metadata_shared_intent, "metadata"
    if SHARED_MEMORY_RE.search(normalize_sentence(user_text)):
        return True, "natural_language"
    return False, "none"


def select_durable_layer(candidate: CandidateMemory, namespace: NamespaceContext) -> str | None:
    if candidate.confidence < 0.8:
        return None
    # dslm_agent hard block: Gateway users MUST NOT write semantic_user ever
    if namespace.is_gateway:
        return "semantic_shared" if namespace.durable_shared_allowed else None
    if namespace.durable_user_allowed:
        return "semantic_user"
    if namespace.durable_shared_allowed:
        return "semantic_shared"
    return None


def rank_record(
    base_score: float,
    *,
    reinforcement_count: int,
    access_count: int,
    archived: bool,
) -> float:
    if archived:
        return base_score * 0.25
    return base_score + (reinforcement_count * 0.15) + (access_count * 0.05)


def find_superseded(records: Iterable[dict], candidate: CandidateMemory) -> str | None:
    candidate_words = set(candidate.content.lower().split())
    for record in records:
        content = str(record.get("content", ""))
        words = set(content.lower().split())
        overlap = len(candidate_words & words) / max(1, min(len(candidate_words), len(words)))
        if overlap >= 0.75 and content.strip() != candidate.content.strip():
            return str(record["id"])
    return None

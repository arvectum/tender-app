from __future__ import annotations

from difflib import SequenceMatcher


def token_jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    union = len(left.union(right))
    if union == 0:
        return 0.0
    return len(left.intersection(right)) / union


def fuzzy_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()

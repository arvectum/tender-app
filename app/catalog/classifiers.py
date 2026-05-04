from __future__ import annotations

from collections import Counter

from app.catalog.dictionaries import CatalogDictionaries


def classify_category(tokens: list[str], dictionaries: CatalogDictionaries) -> tuple[str | None, float]:
    if not tokens:
        return None, 0.0

    token_text = " ".join(tokens)
    scores: Counter[str] = Counter()
    for category, payload in dictionaries.categories.items():
        keywords = [str(x).lower() for x in (payload or {}).get("keywords", [])]
        for keyword in keywords:
            if keyword in token_text:
                scores[category] += 1

    if not scores:
        return None, 0.0

    best, score = scores.most_common(1)[0]
    confidence = min(1.0, 0.45 + 0.15 * score)
    return best, confidence

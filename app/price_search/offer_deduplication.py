from __future__ import annotations

from app.price_search.base import MarketOfferCandidate


def deduplicate_offers(candidates: list[MarketOfferCandidate]) -> tuple[list[MarketOfferCandidate], list[MarketOfferCandidate]]:
    by_url: dict[str, MarketOfferCandidate] = {}
    duplicates: list[MarketOfferCandidate] = []

    for candidate in candidates:
        url_key = (candidate.url or "").strip().lower()
        if url_key:
            current = by_url.get(url_key)
            if current is None:
                by_url[url_key] = candidate
            else:
                winner, loser = _pick_better_offer(current, candidate)
                by_url[url_key] = winner
                loser.risk_flags.append("duplicate")
                duplicates.append(loser)
        else:
            synthetic_key = _fallback_key(candidate)
            current = by_url.get(synthetic_key)
            if current is None:
                by_url[synthetic_key] = candidate
            else:
                winner, loser = _pick_better_offer(current, candidate)
                by_url[synthetic_key] = winner
                loser.risk_flags.append("duplicate")
                duplicates.append(loser)

    unique = list(by_url.values())
    return unique, duplicates


def _fallback_key(candidate: MarketOfferCandidate) -> str:
    seller = (candidate.seller_name or "").strip().lower()
    title = candidate.title.strip().lower()
    return f"{seller}|{title}|{candidate.unit_price}"


def _pick_better_offer(left: MarketOfferCandidate, right: MarketOfferCandidate) -> tuple[MarketOfferCandidate, MarketOfferCandidate]:
    left_score = _dedupe_priority_score(left)
    right_score = _dedupe_priority_score(right)
    if right_score > left_score:
        return right, left
    return left, right


def _dedupe_priority_score(candidate: MarketOfferCandidate) -> float:
    score = 0.0
    delivery = candidate.delivery_price if candidate.delivery_price is not None else 10_000
    score += max(0.0, 10_000 - float(delivery)) / 10_000
    if candidate.region:
        score += 0.2
    score += min(float(candidate.available_quantity), 10_000.0) / 10_000
    score += candidate.relevance_score
    return score

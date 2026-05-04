from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.services.schemas import ItemOptimizationResult, OfferSnapshot, SelectedOfferPortion


@dataclass
class _DPState:
    cost: Decimal
    selections: dict[int, int]
    unknown_delivery_used: bool


def optimize_item_cost(
    required_quantity: int,
    offers: list[OfferSnapshot],
    default_unknown_delivery_cost: Decimal,
) -> ItemOptimizationResult:
    if required_quantity <= 0:
        return ItemOptimizationResult(
            status="calculated",
            required_quantity=required_quantity,
            covered_quantity=required_quantity,
            estimated_cost=Decimal("0"),
            unknown_delivery_used=False,
            selected_offers=[],
        )

    if not offers:
        return ItemOptimizationResult(
            status="no_relevant_offers",
            required_quantity=required_quantity,
            covered_quantity=0,
            estimated_cost=None,
            unknown_delivery_used=False,
            selected_offers=[],
        )

    dp: dict[int, _DPState] = {0: _DPState(cost=Decimal("0"), selections={}, unknown_delivery_used=False)}

    for idx, offer in enumerate(offers):
        next_dp = dict(dp)
        delivery_price = offer.delivery_price if offer.delivery_price is not None else default_unknown_delivery_cost
        delivery_unknown = offer.delivery_price is None

        for current_qty, state in dp.items():
            max_for_offer = min(offer.available_quantity, required_quantity - current_qty)
            for take_qty in range(1, max_for_offer + 1):
                new_qty = current_qty + take_qty
                incremental_cost = (offer.unit_price * take_qty) + delivery_price
                new_cost = state.cost + incremental_cost
                existing = next_dp.get(new_qty)

                if existing is None or new_cost < existing.cost:
                    new_selections = dict(state.selections)
                    new_selections[idx] = take_qty
                    next_dp[new_qty] = _DPState(
                        cost=new_cost,
                        selections=new_selections,
                        unknown_delivery_used=state.unknown_delivery_used or delivery_unknown,
                    )

        dp = next_dp

    if required_quantity in dp:
        result_state = dp[required_quantity]
        selected_offers = _materialize_selected_offers(
            result_state.selections,
            offers,
            default_unknown_delivery_cost=default_unknown_delivery_cost,
        )
        return ItemOptimizationResult(
            status="calculated",
            required_quantity=required_quantity,
            covered_quantity=required_quantity,
            estimated_cost=result_state.cost,
            unknown_delivery_used=result_state.unknown_delivery_used,
            selected_offers=selected_offers,
        )

    best_quantity = max(dp)
    best_state = dp[best_quantity]
    selected_offers = _materialize_selected_offers(
        best_state.selections,
        offers,
        default_unknown_delivery_cost=default_unknown_delivery_cost,
    )
    return ItemOptimizationResult(
        status="insufficient_market_quantity",
        required_quantity=required_quantity,
        covered_quantity=best_quantity,
        estimated_cost=best_state.cost,
        unknown_delivery_used=best_state.unknown_delivery_used,
        selected_offers=selected_offers,
    )


def _materialize_selected_offers(
    selections: dict[int, int],
    offers: list[OfferSnapshot],
    default_unknown_delivery_cost: Decimal,
) -> list[SelectedOfferPortion]:
    portions: list[SelectedOfferPortion] = []
    for offer_index, used_quantity in selections.items():
        offer = offers[offer_index]
        delivery_price = offer.delivery_price if offer.delivery_price is not None else default_unknown_delivery_cost
        portions.append(
            SelectedOfferPortion(
                offer_id=offer.offer_id,
                supplier_name=offer.supplier_name,
                used_quantity=used_quantity,
                unit_price=offer.unit_price,
                delivery_price=delivery_price,
                delivery_price_was_default=offer.delivery_price is None,
            )
        )
    portions.sort(key=lambda part: (part.supplier_name, part.unit_price))
    return portions

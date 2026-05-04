from __future__ import annotations

import json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import and_, asc, desc, func, or_, select, text
from sqlalchemy.orm import Session, selectinload

from app.config import get_required_no_proxy_hosts, get_settings
from app.db import get_session
from app.models import (
    AuditLog,
    BusinessRule,
    CalculationOfferUsage,
    DashboardNotification,
    ItemAttributes,
    ItemCostCalculation,
    JobRun,
    MarketOffer,
    ParticipationStrategy,
    Purchase,
    PurchaseCalculation,
    PurchaseDecisionScore,
    PurchaseItem,
    PurchaseWatchlist,
    Supplier,
    User,
)
from app.price_search.query_builder import build_search_query
from app.scheduler import is_scheduler_running
from app.security.auth import require_roles
from app.security.permissions import ADMIN, OPERATOR, VIEWER
from app.security.redaction import redact_mapping
from app.security.sessions import clear_session_cookie, create_session_cookie, get_session_claims, validate_csrf
from app.services.backup_service import backup_file_stats, list_backups, restore_backup
from app.services.audit_service import write_audit_log
from app.services.business_rules_service import BusinessRulesService
from app.services.calculation_service import calculate_purchase
from app.services.deadline_service import get_deadline_soon_purchases
from app.services.decision_service import DecisionService
from app.services.explanation_service import build_purchase_explanation
from app.services.item_attribute_service import ItemAttributeService
from app.services.job_service import get_job_stats
from app.services.rematch_service import rematch_offers
from app.services.supplier_service import SupplierService
from app.services.user_service import UserService
from app.services.watchlist_service import WatchlistService
from app.utils.time import utc_now
from app.scoring.strategy import activate_strategy, get_active_strategy, list_strategies
from app.reports.daily_digest import generate_daily_digest
from app.version import get_version

app = FastAPI(title="Tender Small Volume Calculator")

TEMPLATES_DIR = Path(__file__).resolve().parent / "dashboard" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

WRITE_ROLES = {ADMIN, OPERATOR}
ADMIN_ONLY = {ADMIN}
READ_ROLES = {ADMIN, OPERATOR, VIEWER}


@app.middleware("http")
async def host_and_auth_middleware(request: Request, call_next):
    settings = get_settings()
    public_paths = {"/health", "/login"}
    host = (request.headers.get("host") or "").split(":")[0]
    if settings.dashboard_allowed_hosts and host and host not in settings.dashboard_allowed_hosts:
        return JSONResponse(status_code=400, content={"detail": "Host is not allowed"})

    if settings.dashboard_auth_enabled:
        is_public = request.url.path in public_paths or request.url.path.startswith("/docs") or request.url.path.startswith("/openapi")
        if not is_public:
            claims = get_session_claims(request)
            if claims is None:
                if request.url.path.startswith("/api"):
                    return JSONResponse(status_code=401, content={"detail": "Authentication required"})
                return RedirectResponse(url="/login", status_code=303)

    if request.method not in {"GET", "HEAD", "OPTIONS"} and settings.dashboard_auth_enabled and request.url.path not in public_paths:
        if not validate_csrf(request):
            return JSONResponse(status_code=403, content={"detail": "CSRF validation failed"})

    return await call_next(request)


def _require(
    request: Request,
    session: Session,
    roles: set[str] = READ_ROLES,
    api_mode: bool = False,
):
    return require_roles(request=request, session=session, roles=roles, api_mode=api_mode)


def _template(request: Request, name: str, context: dict, status_code: int = 200) -> HTMLResponse:
    user = context.get("user")
    base = {"request": request, "current_user": user, "app_version": get_version()}
    base.update(context)
    return templates.TemplateResponse(request, name, base, status_code=status_code)


@app.get("/health")
def health(session: Session = Depends(get_session)) -> dict[str, str]:
    settings = get_settings()
    database_status = "ok"
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        database_status = "fail"

    scheduler_state = "running" if is_scheduler_running() else "unknown"
    if settings.scheduler_enabled and not is_scheduler_running():
        scheduler_state = "not_running"

    return {
        "status": "ok" if database_status == "ok" else "degraded",
        "database": database_status,
        "version": get_version(),
        "time": utc_now().isoformat(),
        "scheduler": scheduler_state,
    }


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    if not get_settings().dashboard_auth_enabled:
        return RedirectResponse(url="/", status_code=303)
    return _template(request, "login.html", {"error": None})


@app.post("/login")
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    session: Session = Depends(get_session),
) -> Response:
    if not get_settings().dashboard_auth_enabled:
        return RedirectResponse(url="/", status_code=303)
    user = UserService(session).authenticate(username=username, password=password)
    if user is None:
        return _template(request, "login.html", {"error": "Invalid credentials"}, status_code=401)
    response = RedirectResponse(url="/", status_code=303)
    create_session_cookie(response, user_id=user.id, username=user.username, role=user.role)
    return response


@app.post("/logout")
def logout() -> Response:
    response = RedirectResponse(url="/login", status_code=303)
    clear_session_cookie(response)
    return response


@app.get("/", response_class=HTMLResponse)
def dashboard_home(
    request: Request,
    sort_by: str = Query("score_desc"),
    source: str | None = Query(None),
    status: str | None = Query(None),
    region: str | None = Query(None),
    recommendation_status: str | None = Query(None),
    has_problem_items: bool = Query(False),
    price_not_found: bool = Query(False),
    needs_manual_review: bool = Query(False),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    user = _require(request, session, READ_ROLES)
    stmt = (
        select(Purchase, PurchaseCalculation, PurchaseDecisionScore, PurchaseWatchlist)
        .outerjoin(PurchaseCalculation, PurchaseCalculation.purchase_id == Purchase.id)
        .outerjoin(PurchaseDecisionScore, PurchaseDecisionScore.purchase_id == Purchase.id)
        .outerjoin(PurchaseWatchlist, PurchaseWatchlist.purchase_id == Purchase.id)
    )

    if source:
        stmt = stmt.where(Purchase.source == source)
    if status:
        stmt = stmt.where(Purchase.status == status)
    if region:
        stmt = stmt.where(Purchase.region == region)
    if recommendation_status:
        stmt = stmt.where(PurchaseCalculation.recommendation_status == recommendation_status)

    if has_problem_items:
        stmt = stmt.where(PurchaseCalculation.problematic_items_count > 0)
    if price_not_found:
        subq = (
            select(ItemCostCalculation.purchase_id)
            .where(ItemCostCalculation.status.in_(["no_relevant_offers", "needs_manual_price_search"]))
            .group_by(ItemCostCalculation.purchase_id)
        )
        stmt = stmt.where(Purchase.id.in_(subq))
    if needs_manual_review:
        subq_manual = (
            select(ItemCostCalculation.purchase_id)
            .where(ItemCostCalculation.status.in_(["needs_manual_review", "needs_manual_price_search", "delivery_unknown"]))
            .group_by(ItemCostCalculation.purchase_id)
        )
        stmt = stmt.where(Purchase.id.in_(subq_manual))

    if sort_by == "margin_desc":
        stmt = stmt.order_by(desc(PurchaseCalculation.margin_percent).nullslast())
    elif sort_by == "profit_desc":
        stmt = stmt.order_by(desc(PurchaseCalculation.estimated_profit).nullslast())
    elif sort_by == "deadline_asc":
        stmt = stmt.order_by(asc(Purchase.submission_deadline).nullslast())
    elif sort_by == "max_price_desc":
        stmt = stmt.order_by(desc(Purchase.max_total_price).nullslast())
    else:
        stmt = stmt.order_by(desc(PurchaseCalculation.attractiveness_score).nullslast())

    rows_raw = session.execute(stmt).all()
    rows = [
        {
            "purchase": purchase,
            "calc": calc,
            "decision_score": decision_score,
            "watchlist": watchlist,
        }
        for purchase, calc, decision_score, watchlist in rows_raw
    ]
    risky_supplier_counts = dict(
        session.execute(
            select(MarketOffer.purchase_id, func.count(MarketOffer.id))
            .where(MarketOffer.supplier_status == "risky")
            .group_by(MarketOffer.purchase_id)
        ).all()
    )

    latest_jobs_by_type: dict[str, JobRun] = {}
    latest_jobs = session.scalars(select(JobRun).order_by(JobRun.created_at.desc()).limit(200)).all()
    for job in latest_jobs:
        latest_jobs_by_type.setdefault(job.job_type, job)

    source_options = session.scalars(select(Purchase.source).distinct().order_by(Purchase.source)).all()
    status_options = session.scalars(select(Purchase.status).distinct().order_by(Purchase.status)).all()
    region_options = session.scalars(select(Purchase.region).distinct().order_by(Purchase.region)).all()
    recommendation_options = session.scalars(
        select(PurchaseCalculation.recommendation_status).distinct().order_by(PurchaseCalculation.recommendation_status)
    ).all()
    top_opportunities = DecisionService(session).get_top_opportunities(limit=5)
    strong_recommend_count = session.scalar(
        select(func.count(PurchaseDecisionScore.id)).where(PurchaseDecisionScore.decision == "strong_recommend")
    ) or 0
    needs_review_count = session.scalar(
        select(func.count(PurchaseDecisionScore.id)).where(PurchaseDecisionScore.decision == "needs_manual_review")
    ) or 0
    deadline_soon_count = session.scalar(
        select(func.count(PurchaseDecisionScore.id)).where(PurchaseDecisionScore.deadline_status == "deadline_soon")
    ) or 0
    watchlist_active_count = session.scalar(
        select(func.count(PurchaseWatchlist.id)).where(PurchaseWatchlist.status.in_(["watch", "preparing", "submitted"]))
    ) or 0
    failed_jobs_count = session.scalar(
        select(func.count(JobRun.id)).where(JobRun.status == "failed", JobRun.created_at >= (utc_now() - timedelta(hours=24)))
    ) or 0
    latest_digest = generate_daily_digest(session, send=False)
    prices_missing_count = session.scalar(
        select(func.count(func.distinct(ItemCostCalculation.purchase_id))).where(
            ItemCostCalculation.status.in_(["no_relevant_offers", "needs_manual_price_search"])
        )
    ) or 0
    low_data_quality_count = session.scalar(
        select(func.count(Purchase.id)).where(Purchase.data_quality == "low")
    ) or 0
    high_risk_count = session.scalar(
        select(func.count(PurchaseDecisionScore.id)).where(PurchaseDecisionScore.risk_level.in_(["high", "critical"]))
    ) or 0
    approve_decisions_count = session.scalar(
        select(func.count(PurchaseDecisionScore.id)).where(PurchaseDecisionScore.decision_status.in_(["draft", "needs_review"]))
    ) or 0

    return _template(
        request,
        "index.html",
        {
            "user": user,
            "rows": rows,
            "sort_by": sort_by,
            "source": source,
            "status": status,
            "region": region,
            "recommendation_status": recommendation_status,
            "has_problem_items": has_problem_items,
            "price_not_found": price_not_found,
            "needs_manual_review": needs_manual_review,
            "source_options": [value for value in source_options if value],
            "status_options": [value for value in status_options if value],
            "region_options": [value for value in region_options if value],
            "recommendation_options": [value for value in recommendation_options if value],
            "latest_jobs_by_type": latest_jobs_by_type,
            "risky_supplier_counts": risky_supplier_counts,
            "top_opportunities": top_opportunities,
            "strong_recommend_count": strong_recommend_count,
            "needs_review_count": needs_review_count,
            "deadline_soon_count": deadline_soon_count,
            "watchlist_active_count": watchlist_active_count,
            "failed_jobs_count": failed_jobs_count,
            "latest_digest": latest_digest,
            "next_actions": {
                "fill_prices": prices_missing_count,
                "check_low_data_quality": low_data_quality_count,
                "check_high_risk": high_risk_count,
                "approve_decisions": approve_decisions_count,
            },
        }
    )


@app.post("/purchases/{purchase_id}/recalculate")
def purchase_recalculate(request: Request, purchase_id: int, session: Session = Depends(get_session)) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    calculate_purchase(session, purchase_id)
    write_audit_log(
        session=session,
        entity_type="purchase",
        entity_id=str(purchase_id),
        action="recalculate",
        comment="manual recalculate from dashboard",
    )
    return RedirectResponse(url=f"/purchases/{purchase_id}", status_code=303)


@app.get("/purchases/{purchase_id}", response_class=HTMLResponse)
def purchase_detail(
    purchase_id: int,
    request: Request,
    offers_view: str = Query("all"),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    user = _require(request, session, READ_ROLES)
    purchase = session.scalar(
        select(Purchase)
        .where(Purchase.id == purchase_id)
        .options(
            selectinload(Purchase.items).selectinload(PurchaseItem.attributes),
            selectinload(Purchase.item_calculations),
            selectinload(Purchase.calculation),
        )
    )
    if purchase is None:
        return _template(request, "not_found.html", {"purchase_id": purchase_id}, status_code=404)

    calculations = session.scalars(
        select(ItemCostCalculation).where(ItemCostCalculation.purchase_id == purchase.id)
    ).all()
    item_calc_map = {calc.purchase_item_id: calc for calc in calculations}

    usage_rows = session.scalars(
        select(CalculationOfferUsage).where(CalculationOfferUsage.item_cost_calculation_id.in_([calc.id for calc in calculations]))
    ).all() if calculations else []
    usage_by_offer_id = {row.market_offer_id: row for row in usage_rows if row.market_offer_id is not None}

    offer_stmt = select(MarketOffer).where(MarketOffer.purchase_id == purchase.id)
    if offers_view == "used":
        offer_stmt = offer_stmt.where(MarketOffer.id.in_(list(usage_by_offer_id.keys()) or [-1]))
    elif offers_view == "irrelevant":
        offer_stmt = offer_stmt.where(MarketOffer.is_relevant.is_(False))

    offers = session.scalars(offer_stmt.order_by(MarketOffer.purchase_item_id.asc(), MarketOffer.effective_unit_price.asc())).all()
    offers_by_item: dict[int, list[dict]] = {}
    for offer in offers:
        item_key = offer.purchase_item_id or -1
        usage = usage_by_offer_id.get(offer.id)
        effective_relevant = resolve_offer_relevance(offer)
        offers_by_item.setdefault(item_key, []).append(
            {
                "offer": offer,
                "used": usage is not None,
                "taken_quantity": usage.taken_quantity if usage else None,
                "used_total": usage.total_cost if usage else None,
                "effective_relevant": effective_relevant,
            }
        )

    search_queries = {item.id: build_search_query(item) for item in purchase.items}
    can_view_raw = user.role in {ADMIN, OPERATOR}
    raw_payload_pretty = json.dumps(purchase.raw_payload, ensure_ascii=False, indent=2) if (purchase.raw_payload and can_view_raw) else None
    explanation = build_purchase_explanation(session, purchase.id)
    decision_score = session.scalar(select(PurchaseDecisionScore).where(PurchaseDecisionScore.purchase_id == purchase.id))
    item_ids = [str(item.id) for item in purchase.items]
    offer_ids = [str(offer.id) for offer in offers]
    audit_rows = session.scalars(
        select(AuditLog)
        .where(
            or_(
                (AuditLog.entity_type == "purchase") & (AuditLog.entity_id == str(purchase.id)),
                (AuditLog.entity_type == "purchase_item") & (AuditLog.entity_id.in_(item_ids or ["-1"])),
                (AuditLog.entity_type == "market_offer") & (AuditLog.entity_id.in_(offer_ids or ["-1"])),
                (AuditLog.entity_type == "watchlist") & (AuditLog.entity_id == str(purchase.id)),
            )
        )
        .order_by(AuditLog.created_at.desc())
        .limit(40)
    ).all()

    return _template(
        request,
        "purchase_detail.html",
        {
            "user": user,
            "purchase": purchase,
            "item_calc_map": item_calc_map,
            "purchase_calc": purchase.calculation,
            "raw_payload_pretty": raw_payload_pretty,
            "can_view_raw": can_view_raw,
            "is_fixture": purchase.source == "fixture",
            "offers_view": offers_view,
            "offers_by_item": offers_by_item,
            "search_queries": search_queries,
            "explanation": explanation,
            "decision_score": decision_score,
            "audit_rows": audit_rows,
            "data_quality_warnings": purchase.data_quality_warnings_json or [],
        }
    )


@app.post("/items/{item_id}/refresh-attributes")
def refresh_item_attributes(request: Request, item_id: int, purchase_id: int = Form(...), session: Session = Depends(get_session)) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    ItemAttributeService(session).refresh_attributes(item_id)
    write_audit_log(
        session=session,
        entity_type="purchase_item",
        entity_id=str(item_id),
        action="refresh_attributes",
        comment="manual refresh from dashboard",
    )
    return RedirectResponse(url=f"/purchases/{purchase_id}", status_code=303)


@app.post("/items/{item_id}/rematch-offers")
def rematch_item_offers(request: Request, item_id: int, purchase_id: int = Form(...), session: Session = Depends(get_session)) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    rematch_offers(session, item_id=item_id)
    write_audit_log(
        session=session,
        entity_type="purchase_item",
        entity_id=str(item_id),
        action="rematch_offers",
        comment="manual rematch from dashboard",
    )
    calculate_purchase(session, purchase_id)
    return RedirectResponse(url=f"/purchases/{purchase_id}", status_code=303)


@app.post("/offers/{offer_id}/mark-relevant")
def mark_offer_relevant(request: Request, offer_id: int, purchase_id: int = Form(...), session: Session = Depends(get_session)) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    return _update_offer_override(session, offer_id, purchase_id, action="mark_relevant", manual_relevance=True)


@app.post("/offers/{offer_id}/mark-irrelevant")
def mark_offer_irrelevant(request: Request, offer_id: int, purchase_id: int = Form(...), session: Session = Depends(get_session)) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    return _update_offer_override(session, offer_id, purchase_id, action="mark_irrelevant", manual_relevance=False)


@app.post("/offers/{offer_id}/exclude")
def exclude_offer(request: Request, offer_id: int, purchase_id: int = Form(...), session: Session = Depends(get_session)) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    return _update_offer_override(session, offer_id, purchase_id, action="exclude", exclude=True)


@app.post("/offers/{offer_id}/force-include")
def force_include_offer(request: Request, offer_id: int, purchase_id: int = Form(...), session: Session = Depends(get_session)) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    return _update_offer_override(session, offer_id, purchase_id, action="force_include", include=True)


@app.post("/offers/{offer_id}/update")
def update_offer(
    request: Request,
    offer_id: int,
    purchase_id: int = Form(...),
    available_quantity: str | None = Form(None),
    unit_price: str | None = Form(None),
    delivery_price: str | None = Form(None),
    manual_comment: str | None = Form(None),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    offer = session.scalar(select(MarketOffer).where(MarketOffer.id == offer_id))
    if offer is None:
        return RedirectResponse(url=f"/purchases/{purchase_id}", status_code=303)

    old = _offer_snapshot(offer)
    if available_quantity not in (None, ""):
        offer.available_quantity = max(int(float(available_quantity)), 0)
    if unit_price not in (None, ""):
        offer.unit_price = Decimal(str(unit_price))
    if delivery_price not in (None, ""):
        offer.delivery_price = Decimal(str(delivery_price))
    if manual_comment is not None:
        offer.manual_comment = manual_comment
    offer.updated_by_user_at = utc_now()

    session.commit()
    write_audit_log(
        session=session,
        entity_type="market_offer",
        entity_id=str(offer.id),
        action="update",
        old_value_json=old,
        new_value_json=_offer_snapshot(offer),
        comment=manual_comment,
    )

    return RedirectResponse(url=f"/purchases/{purchase_id}", status_code=303)


@app.post("/items/{item_id}/manual-offer")
def add_manual_offer(
    request: Request,
    item_id: int,
    purchase_id: int = Form(...),
    offer_title: str = Form(...),
    seller_name: str | None = Form(None),
    offer_url: str | None = Form(None),
    region: str | None = Form(None),
    unit_price: str = Form(...),
    available_quantity: str = Form("1"),
    delivery_price: str | None = Form(None),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    item = session.scalar(select(PurchaseItem).where(PurchaseItem.id == item_id, PurchaseItem.purchase_id == purchase_id))
    if item is None:
        return RedirectResponse(url=f"/purchases/{purchase_id}", status_code=303)
    offer = MarketOffer(
        provider="manual_dashboard",
        source="manual",
        purchase_id=purchase_id,
        purchase_item_id=item_id,
        item_name=item.item_name,
        offer_title=offer_title,
        offer_url=offer_url,
        seller_name=seller_name,
        supplier_name=seller_name or "manual",
        region=region,
        unit_price=Decimal(str(unit_price)),
        available_quantity=max(int(float(available_quantity)), 0),
        delivery_price=Decimal(str(delivery_price)) if delivery_price not in (None, "") else None,
        effective_unit_price=None,
        relevance_score=Decimal("1.0"),
        is_relevant=True,
        manual_override_relevance=True,
        risk_flags=["manual_force_include"],
        updated_by_user_at=utc_now(),
    )
    session.add(offer)
    session.commit()
    write_audit_log(
        session=session,
        entity_type="market_offer",
        entity_id=str(offer.id),
        action="manual_add",
        new_value_json=_offer_snapshot(offer),
    )
    return RedirectResponse(url=f"/purchases/{purchase_id}", status_code=303)


@app.get("/jobs", response_class=HTMLResponse)
def jobs_page(
    request: Request,
    status: str | None = Query(None),
    job_type: str | None = Query(None),
    source: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    user = _require(request, session, READ_ROLES)
    stmt = select(JobRun)
    conditions = []
    if status:
        conditions.append(JobRun.status == status)
    if job_type:
        conditions.append(JobRun.job_type == job_type)
    if source:
        conditions.append(JobRun.source == source)

    if date_from:
        try:
            conditions.append(JobRun.created_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            conditions.append(JobRun.created_at <= datetime.fromisoformat(date_to))
        except ValueError:
            pass

    if conditions:
        stmt = stmt.where(and_(*conditions))

    jobs = session.scalars(stmt.order_by(desc(JobRun.created_at)).limit(300)).all()

    statuses = session.scalars(select(JobRun.status).distinct().order_by(JobRun.status)).all()
    types = session.scalars(select(JobRun.job_type).distinct().order_by(JobRun.job_type)).all()
    sources = session.scalars(select(JobRun.source).distinct().order_by(JobRun.source)).all()

    return _template(
        request,
        "jobs.html",
        {
            "user": user,
            "jobs": jobs,
            "statuses": [x for x in statuses if x],
            "types": [x for x in types if x],
            "sources": [x for x in sources if x],
            "status_filter": status,
            "type_filter": job_type,
            "source_filter": source,
            "date_from": date_from,
            "date_to": date_to,
        }
    )


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(job_id: int, request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    user = _require(request, session, READ_ROLES)
    job = session.scalar(select(JobRun).where(JobRun.id == job_id))
    if job is None:
        return _template(request, "not_found.html", {"user": user, "purchase_id": job_id}, status_code=404)

    params_pretty = json.dumps(job.params_json, ensure_ascii=False, indent=2) if job.params_json else ""
    result_pretty = json.dumps(job.result_json, ensure_ascii=False, indent=2) if job.result_json else ""

    return _template(
        request,
        "job_detail.html",
        {
            "user": user,
            "job": job,
            "params_pretty": params_pretty,
            "result_pretty": result_pretty,
            "logs_excerpt": _collect_logs_excerpt(),
        }
    )


@app.get("/diagnostics", response_class=HTMLResponse)
def diagnostics_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    user = _require(request, session, READ_ROLES)
    settings = get_settings()

    db_ok = True
    try:
        session.execute(text("SELECT 1"))
    except Exception:
        db_ok = False

    count_purchases = session.scalar(select(func.count(Purchase.id))) or 0
    count_items = session.scalar(select(func.count(PurchaseItem.id))) or 0
    count_offers = session.scalar(select(func.count(MarketOffer.id))) or 0
    count_recommended = session.scalar(select(func.count(PurchaseCalculation.id)).where(PurchaseCalculation.recommendation_status == "ok")) or 0
    count_needs_review = session.scalar(select(func.count(PurchaseCalculation.id)).where(PurchaseCalculation.recommendation_status == "needs_review")) or 0

    last_parse_mos = session.scalar(
        select(JobRun).where(JobRun.job_type == "parse", JobRun.source == "mos_portal").order_by(JobRun.created_at.desc()).limit(1)
    )
    last_parse_eat = session.scalar(
        select(JobRun).where(JobRun.job_type == "parse", JobRun.source == "eat").order_by(JobRun.created_at.desc()).limit(1)
    )
    last_calculate = session.scalar(select(JobRun).where(JobRun.job_type == "calculate").order_by(JobRun.created_at.desc()).limit(1))
    last_export = session.scalar(select(JobRun).where(JobRun.job_type == "export_excel").order_by(JobRun.created_at.desc()).limit(1))

    stats = get_job_stats(session)

    no_proxy_required = sorted(get_required_no_proxy_hosts())
    no_proxy_missing = [host for host in no_proxy_required if host not in settings.no_proxy]

    from app.browser.session_manager import BrowserSessionManager

    browser_manager = BrowserSessionManager()

    return _template(
        request,
        "diagnostics.html",
        {
            "user": user,
            "db_ok": db_ok,
            "last_parse_mos": last_parse_mos,
            "last_parse_eat": last_parse_eat,
            "last_calculate": last_calculate,
            "last_export": last_export,
            "count_purchases": count_purchases,
            "count_items": count_items,
            "count_offers": count_offers,
            "count_recommended": count_recommended,
            "count_needs_review": count_needs_review,
            "failed_jobs_last_24h": stats.get("failed_last_day", 0),
            "no_proxy": redact_mapping({"no_proxy": ",".join(settings.no_proxy)})["no_proxy"],
            "no_proxy_missing": no_proxy_missing,
            "browser_state_mos_exists": browser_manager.state_exists("mos_portal"),
            "browser_state_eat_exists": browser_manager.state_exists("eat"),
            "scheduler_status": "running" if is_scheduler_running() else "not_running",
        }
    )


@app.get("/backups", response_class=HTMLResponse)
def backups_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    user = _require(request, session, READ_ROLES)
    backups = backup_file_stats()
    return _template(request, "backups.html", {"user": user, "backups": backups})


@app.post("/backups/restore")
def backups_restore(
    request: Request,
    file_path: str = Form(...),
    yes: bool = Form(False),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    _require(request, session, ADMIN_ONLY)
    try:
        restore_backup(Path(file_path), yes=yes)
        write_audit_log(
            session=session,
            entity_type="backup",
            entity_id=file_path,
            action="restore",
            comment="restore via dashboard",
        )
    except Exception as exc:  # noqa: BLE001
        write_audit_log(
            session=session,
            entity_type="backup",
            entity_id=file_path,
            action="restore_failed",
            comment=str(exc),
        )
    return RedirectResponse(url="/backups", status_code=303)


@app.get("/backups/download")
def backups_download(request: Request, path: str, session: Session = Depends(get_session)):
    _require(request, session, READ_ROLES)
    file_path = Path(path)
    if not file_path.exists():
        return JSONResponse(status_code=404, content={"detail": "Backup file not found"})
    return FileResponse(file_path)


@app.get("/export/current-view")
def export_current_view(
    request: Request,
    source: str | None = Query(None),
    status: str | None = Query(None),
    region: str | None = Query(None),
    recommendation_status: str | None = Query(None),
    session: Session = Depends(get_session),
) -> dict[str, str]:
    _require(request, session, READ_ROLES, api_mode=True)
    from openpyxl import Workbook

    stmt = select(Purchase, PurchaseCalculation).outerjoin(PurchaseCalculation, PurchaseCalculation.purchase_id == Purchase.id)
    if source:
        stmt = stmt.where(Purchase.source == source)
    if status:
        stmt = stmt.where(Purchase.status == status)
    if region:
        stmt = stmt.where(Purchase.region == region)
    if recommendation_status:
        stmt = stmt.where(PurchaseCalculation.recommendation_status == recommendation_status)

    rows = session.execute(stmt).all()

    exports_dir = get_settings().project_root / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    output_path = exports_dir / f"dashboard_view_{utc_now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    wb = Workbook()
    ws = wb.active
    ws.title = "CurrentView"
    ws.append(["purchase_id", "source", "external_id", "title", "status", "region", "estimated_cost", "margin_percent", "recommendation"])
    for purchase, calc in rows:
        ws.append([
            purchase.id,
            purchase.source,
            purchase.external_id,
            purchase.title,
            purchase.status,
            purchase.region,
            float(calc.estimated_cost) if calc else None,
            float(calc.margin_percent) if calc else None,
            calc.recommendation_status if calc else None,
        ])
    wb.save(output_path)

    return {"status": "ok", "file": str(output_path)}


@app.get("/suppliers", response_class=HTMLResponse)
def suppliers_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    user = _require(request, session, READ_ROLES)
    suppliers = session.scalars(select(Supplier).order_by(Supplier.name.asc())).all()
    return _template(request, "suppliers.html", {"user": user, "suppliers": suppliers})


@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    user = _require(request, session, ADMIN_ONLY)
    rows = session.scalars(select(User).order_by(User.username.asc())).all()
    return _template(request, "users.html", {"user": user, "rows": rows})


@app.post("/users/{user_id}/toggle")
def users_toggle(request: Request, user_id: int, is_active: bool = Form(...), session: Session = Depends(get_session)) -> RedirectResponse:
    _require(request, session, ADMIN_ONLY)
    row = session.scalar(select(User).where(User.id == user_id))
    if row is not None:
        row.is_active = is_active
        session.commit()
        write_audit_log(
            session=session,
            entity_type="user",
            entity_id=str(row.id),
            action="toggle_active",
            new_value_json={"is_active": row.is_active},
        )
    return RedirectResponse(url="/users", status_code=303)


@app.post("/suppliers/{supplier_id}/update")
def supplier_update(request: Request, supplier_id: int, status: str = Form(...), comment: str | None = Form(None), session: Session = Depends(get_session)) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    supplier = session.scalar(select(Supplier).where(Supplier.id == supplier_id))
    if supplier is None:
        return RedirectResponse(url="/suppliers", status_code=303)
    old_status = supplier.status
    supplier.status = status
    if comment is not None:
        supplier.comment = comment
    session.commit()
    write_audit_log(
        session=session,
        entity_type="supplier",
        entity_id=str(supplier.id),
        action="update_status",
        old_value_json={"status": old_status},
        new_value_json={"status": supplier.status, "comment": supplier.comment},
    )
    return RedirectResponse(url="/suppliers", status_code=303)


@app.get("/settings/business-rules", response_class=HTMLResponse)
def business_rules_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    user = _require(request, session, READ_ROLES)
    service = BusinessRulesService(session)
    defaults = service.defaults_map()
    existing = {row.key: row for row in service.list_rules()}
    rows = []
    for key, default in defaults.items():
        row = existing.get(key)
        rows.append(
            {
                "key": key,
                "value": row.value if row else default,
                "source": "db" if row else "env",
                "description": row.description if row else "",
            }
        )
    return _template(request, "business_rules.html", {"user": user, "rows": rows, "warning": "Для применения изменений выполните пересчет закупок."})


@app.post("/settings/business-rules")
def business_rules_update(
    request: Request,
    key: str = Form(...),
    value: str = Form(...),
    description: str | None = Form(None),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    service = BusinessRulesService(session)
    old = service.get(key, service.defaults_map().get(key, "")).value
    row = service.set_rule(key=key, value=value, description=description)
    write_audit_log(
        session=session,
        entity_type="business_rule",
        entity_id=str(row.id),
        action="update",
        old_value_json={"value": old},
        new_value_json={"value": row.value},
        comment=row.description,
    )
    return RedirectResponse(url="/settings/business-rules", status_code=303)


@app.get("/strategies", response_class=HTMLResponse)
def strategies_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    user = _require(request, session, READ_ROLES)
    strategies = list_strategies(session)
    active = get_active_strategy(session)
    return _template(request, "strategies.html", {"user": user, "strategies": strategies, "active_name": active.name if active else None})


@app.post("/strategies/activate")
def strategies_activate(request: Request, name: str = Form(...), session: Session = Depends(get_session)) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    old_active = get_active_strategy(session)
    new_active = activate_strategy(session, name=name)
    write_audit_log(
        session=session,
        entity_type="strategy",
        entity_id=str(new_active.id),
        action="activate",
        old_value_json={"active": old_active.name if old_active else None},
        new_value_json={"active": new_active.name},
    )
    return RedirectResponse(url="/strategies", status_code=303)


@app.get("/watchlist", response_class=HTMLResponse)
def watchlist_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    user = _require(request, session, READ_ROLES)
    entries = session.scalars(
        select(PurchaseWatchlist).options(selectinload(PurchaseWatchlist.purchase)).order_by(PurchaseWatchlist.updated_at.desc())
    ).all()
    return _template(request, "watchlist.html", {"user": user, "entries": entries})


@app.post("/purchases/{purchase_id}/watch")
def watch_purchase(
    request: Request,
    purchase_id: int,
    status: str = Form("watch"),
    note: str | None = Form(None),
    session: Session = Depends(get_session),
) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    row = WatchlistService(session).update(purchase_id=purchase_id, status=status, note=note)
    write_audit_log(
        session=session,
        entity_type="watchlist",
        entity_id=str(row.id),
        action="upsert",
        new_value_json={"purchase_id": purchase_id, "status": status, "note": note},
    )
    return RedirectResponse(url=f"/purchases/{purchase_id}", status_code=303)


@app.post("/purchases/{purchase_id}/watch/remove")
def unwatch_purchase(request: Request, purchase_id: int, session: Session = Depends(get_session)) -> RedirectResponse:
    _require(request, session, WRITE_ROLES)
    removed = WatchlistService(session).remove(purchase_id)
    if removed:
        write_audit_log(
            session=session,
            entity_type="watchlist",
            entity_id=str(purchase_id),
            action="remove",
            comment="manual remove from dashboard",
        )
    return RedirectResponse(url=f"/purchases/{purchase_id}", status_code=303)


@app.get("/notifications", response_class=HTMLResponse)
def notifications_page(request: Request, unread_only: bool = Query(False), session: Session = Depends(get_session)) -> HTMLResponse:
    user = _require(request, session, READ_ROLES)
    stmt = select(DashboardNotification)
    if unread_only:
        stmt = stmt.where(DashboardNotification.status == "unread")
    rows = session.scalars(stmt.order_by(DashboardNotification.created_at.desc()).limit(500)).all()
    return _template(request, "notifications.html", {"user": user, "rows": rows, "unread_only": unread_only})


@app.post("/notifications/{notification_id}/read")
def notification_mark_read(request: Request, notification_id: int, session: Session = Depends(get_session)) -> RedirectResponse:
    _require(request, session, READ_ROLES)
    row = session.scalar(select(DashboardNotification).where(DashboardNotification.id == notification_id))
    if row is not None:
        row.status = "read"
        row.read_at = utc_now()
        session.commit()
    return RedirectResponse(url="/notifications", status_code=303)


@app.get("/reports/daily", response_class=HTMLResponse)
def daily_report_page(request: Request, session: Session = Depends(get_session)) -> HTMLResponse:
    user = _require(request, session, READ_ROLES)
    digest = generate_daily_digest(session, send=False)
    return _template(request, "daily_report.html", {"user": user, "digest": digest})


@app.get("/risks", response_class=HTMLResponse)
def risks_page(
    request: Request,
    risk_level: str | None = Query(None),
    source: str | None = Query(None),
    category: str | None = Query(None),
    deadline: str | None = Query(None),
    session: Session = Depends(get_session),
) -> HTMLResponse:
    user = _require(request, session, READ_ROLES)
    stmt = (
        select(Purchase, PurchaseDecisionScore)
        .join(PurchaseDecisionScore, PurchaseDecisionScore.purchase_id == Purchase.id)
        .where(PurchaseDecisionScore.risk_level.in_(["high", "critical"]))
    )
    if risk_level:
        stmt = stmt.where(PurchaseDecisionScore.risk_level == risk_level)
    if source:
        stmt = stmt.where(Purchase.source == source)
    if deadline == "soon":
        stmt = stmt.where(PurchaseDecisionScore.deadline_status == "deadline_soon")
    rows = session.execute(stmt.order_by(PurchaseDecisionScore.score_risk.desc()).limit(300)).all()

    hard_reject_count = session.scalar(
        select(func.count(MarketOffer.id)).where(MarketOffer.hard_reject_reason.is_not(None))
    ) or 0
    unknown_delivery_count = session.scalar(select(func.count(MarketOffer.id)).where(MarketOffer.delivery_unknown.is_(True))) or 0
    risky_supplier_count = session.scalar(select(func.count(MarketOffer.id)).where(MarketOffer.supplier_status == "risky")) or 0
    insufficient_count = session.scalar(
        select(func.count(ItemCostCalculation.id)).where(ItemCostCalculation.status == "insufficient_market_quantity")
    ) or 0
    no_price_count = session.scalar(
        select(func.count(ItemCostCalculation.id)).where(ItemCostCalculation.status.in_(["no_relevant_offers", "needs_manual_price_search"]))
    ) or 0

    return _template(
        request,
        "risks.html",
        {
            "user": user,
            "rows": rows,
            "hard_reject_count": hard_reject_count,
            "unknown_delivery_count": unknown_delivery_count,
            "risky_supplier_count": risky_supplier_count,
            "insufficient_count": insufficient_count,
            "no_price_count": no_price_count,
            "risk_level": risk_level,
            "source": source,
            "category": category,
            "deadline": deadline,
        }
    )


@app.get("/api/opportunities")
def api_opportunities(request: Request, limit: int = Query(20, ge=1, le=200), session: Session = Depends(get_session)) -> list[dict]:
    _require(request, session, READ_ROLES, api_mode=True)
    service = DecisionService(session)
    rows = service.get_top_opportunities(limit=limit)
    return [
        {
            "purchase_id": row.purchase_id,
            "decision": row.decision,
            "risk_level": row.risk_level,
            "score_total": float(row.score_total),
            "next_action": row.next_action,
            "deadline_status": row.deadline_status,
        }
        for row in rows
    ]


@app.get("/api/purchases/{purchase_id}/decision")
def api_purchase_decision(request: Request, purchase_id: int, session: Session = Depends(get_session)) -> dict:
    _require(request, session, READ_ROLES, api_mode=True)
    row = session.scalar(select(PurchaseDecisionScore).where(PurchaseDecisionScore.purchase_id == purchase_id))
    if row is None:
        return {"status": "not_found", "purchase_id": purchase_id}
    return {
        "status": "ok",
        "purchase_id": purchase_id,
        "decision": row.decision,
        "risk_level": row.risk_level,
        "score_total": float(row.score_total),
        "decision_reason": row.decision_reason,
        "next_action": row.next_action,
        "deadline_status": row.deadline_status,
    }


@app.get("/api/watchlist")
def api_watchlist(request: Request, session: Session = Depends(get_session)) -> list[dict]:
    _require(request, session, READ_ROLES, api_mode=True)
    rows = WatchlistService(session).list()
    return [
        {
            "purchase_id": row.purchase_id,
            "status": row.status,
            "note": row.note,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]


@app.get("/api/notifications")
def api_notifications(request: Request, session: Session = Depends(get_session)) -> list[dict]:
    _require(request, session, READ_ROLES, api_mode=True)
    rows = session.scalars(select(DashboardNotification).order_by(DashboardNotification.created_at.desc()).limit(200)).all()
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "title": row.title,
            "message": row.message,
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]


@app.post("/api/purchases/{purchase_id}/watch")
def api_watch_purchase(request: Request, purchase_id: int, note: str | None = Form(None), session: Session = Depends(get_session)) -> dict:
    _require(request, session, WRITE_ROLES, api_mode=True)
    row = WatchlistService(session).update(purchase_id=purchase_id, status="watch", note=note)
    return {"status": "ok", "purchase_id": row.purchase_id, "watchlist_status": row.status}


@app.post("/api/purchases/{purchase_id}/ignore")
def api_ignore_purchase(request: Request, purchase_id: int, note: str | None = Form(None), session: Session = Depends(get_session)) -> dict:
    _require(request, session, WRITE_ROLES, api_mode=True)
    row = WatchlistService(session).update(purchase_id=purchase_id, status="ignored", note=note)
    return {"status": "ok", "purchase_id": row.purchase_id, "watchlist_status": row.status}


@app.post("/api/purchases/{purchase_id}/reject")
def api_reject_purchase(request: Request, purchase_id: int, note: str | None = Form(None), session: Session = Depends(get_session)) -> dict:
    _require(request, session, WRITE_ROLES, api_mode=True)
    row = WatchlistService(session).update(purchase_id=purchase_id, status="rejected", note=note)
    return {"status": "ok", "purchase_id": row.purchase_id, "watchlist_status": row.status}



def _update_offer_override(
    session: Session,
    offer_id: int,
    purchase_id: int,
    action: str,
    manual_relevance: bool | None = None,
    exclude: bool | None = None,
    include: bool | None = None,
) -> RedirectResponse:
    offer = session.scalar(select(MarketOffer).where(MarketOffer.id == offer_id))
    if offer is None:
        return RedirectResponse(url=f"/purchases/{purchase_id}", status_code=303)

    old = _offer_snapshot(offer)
    if manual_relevance is not None:
        offer.manual_override_relevance = manual_relevance
    if exclude is not None:
        offer.manual_override_exclude = exclude
    if include is not None:
        offer.manual_override_include = include
        if include and "manual_force_include" not in (offer.risk_flags or []):
            offer.risk_flags = sorted(set((offer.risk_flags or []) + ["manual_force_include"]))
    offer.updated_by_user_at = utc_now()

    session.commit()
    write_audit_log(
        session=session,
        entity_type="market_offer",
        entity_id=str(offer.id),
        action=action,
        old_value_json=old,
        new_value_json=_offer_snapshot(offer),
    )

    return RedirectResponse(url=f"/purchases/{purchase_id}", status_code=303)


def _offer_snapshot(offer: MarketOffer) -> dict:
    return {
        "id": offer.id,
        "is_relevant": offer.is_relevant,
        "manual_override_relevance": offer.manual_override_relevance,
        "manual_override_exclude": offer.manual_override_exclude,
        "manual_override_include": offer.manual_override_include,
        "unit_price": str(offer.unit_price),
        "available_quantity": offer.available_quantity,
        "delivery_price": str(offer.delivery_price) if offer.delivery_price is not None else None,
        "manual_comment": offer.manual_comment,
    }


def resolve_offer_relevance(offer: MarketOffer) -> bool:
    if offer.manual_override_exclude:
        return False
    if offer.manual_override_include:
        return True
    if offer.manual_override_relevance is not None:
        return offer.manual_override_relevance
    return offer.is_relevant


def _collect_logs_excerpt(lines_per_file: int = 80) -> str:
    settings = get_settings()
    snippets: list[str] = []
    for filename in ("connectors.log", "import.log"):
        path = settings.logs_dir / filename
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="ignore").splitlines()
            tail = content[-lines_per_file:]
            snippets.append(f"=== {filename} ===")
            snippets.extend(tail)
        except Exception:
            continue
    return "\n".join(snippets)

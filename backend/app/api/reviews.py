"""Оценка гостя после подачи заказа и разбор жалоб в кабинете.

Смысл разделения по оценке: довольного гостя отправляем на публичные карты,
недовольного — во внутреннюю форму, а его жалобу немедленно в чат заведения.
Пока человек не ушёл, проблему ещё можно решить на месте.
"""

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_branch, require_admin
from app.core.db import get_session
from app.models import Branch, Order, OrderStatus, Point, Review, Zone
from app.schemas.admin import AdminReviewOut
from app.services import telegram_notify
from app.services.orders import order_label
from app.services.stats import PERIODS, period_start

router = APIRouter(tags=["reviews"])

# Ниже этого гостя не зовут на публичные карты, а спрашивают, что не так
GOOD_RATING = 4


class ReviewIn(BaseModel):
    order_id: int
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewOut(BaseModel):
    """Что показать гостю после оценки."""

    rating: int
    # ссылка на 2GIS/Google — только для довольных и только если она задана
    review_url: str | None


@router.post("/reviews", response_model=ReviewOut, status_code=201)
async def leave_review(
    body: ReviewIn, session: AsyncSession = Depends(get_session)
):
    """Оценка гостя. Одна на заказ — переголосовать нельзя."""
    order = await session.get(Order, body.order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    if order.status != OrderStatus.served:
        # оценивать нечего, пока заказ не отдали гостю
        raise HTTPException(status_code=409, detail="Заказ ещё не обслужен")

    review = Review(
        branch_id=order.branch_id,
        order_id=order.id,
        rating=body.rating,
        comment=(body.comment or "").strip() or None,
    )
    session.add(review)
    try:
        await session.commit()
    except IntegrityError:
        # unique(order_id): по этому заказу уже оценили
        await session.rollback()
        raise HTTPException(
            status_code=409, detail="Спасибо, оценка по этому заказу уже принята"
        ) from None

    branch = await session.get_one(Branch, order.branch_id)

    if body.rating < GOOD_RATING:
        point = await session.get_one(Point, order.point_id)
        zone_name = await session.scalar(
            select(Zone.name).where(Zone.id == order.zone_id)
        )
        # импорт здесь, а не наверху: _order_actors живёт в гостевом роутере,
        # и на уровне модуля это дало бы кольцо импортов
        from app.api.orders import _order_actors

        actors = await _order_actors(session, order)
        await telegram_notify.notify_bad_review(
            order,
            point,
            zone_name,
            body.rating,
            review.comment,
            actors.get(OrderStatus.accepted),
            actors.get(OrderStatus.served),
        )

    return ReviewOut(
        rating=body.rating,
        review_url=branch.review_url if body.rating >= GOOD_RATING else None,
    )


admin_router = APIRouter(prefix="/admin", tags=["admin"])


@admin_router.get("/reviews", response_model=list[AdminReviewOut])
async def admin_reviews(
    period: str = Query(default="week"),
    limit: int = Query(default=100, ge=1, le=500),
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Отзывы за период, свежие сверху."""
    if period not in PERIODS:
        raise HTTPException(status_code=422, detail=f"period: {', '.join(PERIODS)}")

    stmt = (
        select(Review, Order, Point.label, Zone.name)
        .join(Order, Order.id == Review.order_id)
        .join(Point, Point.id == Order.point_id)
        .outerjoin(Zone, Zone.id == Order.zone_id)
        .where(Review.branch_id == branch.id)
        .order_by(Review.id.desc())
        .limit(limit)
    )
    since = period_start(period)
    if since is not None:
        stmt = stmt.where(Review.created_at >= since)

    rows = (await session.execute(stmt)).all()
    return [
        AdminReviewOut(
            id=review.id,
            created_at=review.created_at,
            rating=review.rating,
            comment=review.comment,
            order_number=order_label(order, zone_name),
            point_label=label,
            order_total=order.total,
            resolved_at=review.resolved_at,
        )
        for review, order, label, zone_name in rows
    ]


@admin_router.post("/reviews/{review_id}/resolve", status_code=204)
async def resolve_review(
    review_id: int,
    _actor: str = Depends(require_admin),
    session: AsyncSession = Depends(get_session),
    branch: Branch = Depends(current_branch),
):
    """Отметить, что с жалобой разобрались — она уходит из сводки."""
    review = await session.get(Review, review_id)
    if review is None or review.branch_id != branch.id:
        raise HTTPException(status_code=404, detail="Отзыв не найден")
    if review.resolved_at is None:
        review.resolved_at = datetime.now(UTC)
        await session.commit()

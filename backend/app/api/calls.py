"""Вызов официанта со стола."""

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models import Point, ServiceCall
from app.services import telegram_notify

logger = logging.getLogger(__name__)

# Пауза между вызовами с одного стола: гость может нервно тапать кнопку,
# а чат заведения от этого засоряться не должен
CALL_COOLDOWN_SEC = 60

router = APIRouter(prefix="/calls", tags=["calls"])


class ServiceCallIn(BaseModel):
    point_token: str
    # что именно нужно гостю: «принести счёт», «пролили чай»
    comment: str | None = Field(default=None, max_length=300)


class ServiceCallOut(BaseModel):
    call_id: int
    # сколько секунд ждать до следующего вызова
    cooldown_sec: int


@router.post("", response_model=ServiceCallOut, status_code=201)
async def call_waiter(
    body: ServiceCallIn, session: AsyncSession = Depends(get_session)
):
    """Позвать официанта к столу — сообщение уходит в чат заведения."""
    point = await session.scalar(
        select(Point).where(
            Point.token == body.point_token, Point.is_archived.is_(False)
        )
    )
    if point is None:
        raise HTTPException(status_code=404, detail="Стол с таким QR-кодом не найден")

    recent = await session.scalar(
        select(ServiceCall.id).where(
            ServiceCall.point_id == point.id,
            ServiceCall.created_at
            >= datetime.now(UTC) - timedelta(seconds=CALL_COOLDOWN_SEC),
        )
    )
    if recent is not None:
        raise HTTPException(
            status_code=429,
            detail="Официант уже вызван, подождите минуту",
            headers={"Retry-After": str(CALL_COOLDOWN_SEC)},
        )

    call = ServiceCall(
        branch_id=point.branch_id,
        point_id=point.id,
        comment=(body.comment or "").strip() or None,
    )
    session.add(call)
    await session.commit()

    message_id = await telegram_notify.notify_service_call(
        call.id, point, call.comment
    )
    if message_id is not None:
        call.tg_message_id = message_id
        await session.commit()

    return ServiceCallOut(call_id=call.id, cooldown_sec=CALL_COOLDOWN_SEC)

"""Repositorio del estado de accountability."""

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Accountability
from app.domain.enums import AccountabilityMode, AccountabilityState


class AccountabilityRepository:
    """Acceso a datos de :class:`Accountability`, acotado por usuario."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, *, user_id: int, task_id: int) -> Accountability | None:
        result = await self._session.execute(
            select(Accountability).where(
                Accountability.user_id == user_id, Accountability.task_id == task_id
            )
        )
        return result.scalar_one_or_none()

    async def get_or_create(
        self,
        *,
        user_id: int,
        task_id: int,
        mode: AccountabilityMode = AccountabilityMode.TRYHARD,
    ) -> Accountability:
        record = await self.get(user_id=user_id, task_id=task_id)
        if record is None:
            record = Accountability(user_id=user_id, task_id=task_id, mode=mode)
            self._session.add(record)
            await self._session.flush()
        return record

    async def update(
        self,
        record: Accountability,
        *,
        state: AccountabilityState | None = None,
        mode: AccountabilityMode | None = None,
        last_reminder_at: datetime | None = None,
        next_reminder_at: datetime | None = None,
        rescue_candidate: bool | None = None,
        increment_reminder_count: bool = False,
    ) -> Accountability:
        if state is not None:
            record.state = state
        if mode is not None:
            record.mode = mode
        if last_reminder_at is not None:
            record.last_reminder_at = last_reminder_at
        if next_reminder_at is not None:
            record.next_reminder_at = next_reminder_at
        if rescue_candidate is not None:
            record.rescue_candidate = rescue_candidate
        if increment_reminder_count:
            record.reminder_count += 1
        await self._session.flush()
        return record

    async def list_rescue_candidates(self, *, user_id: int) -> list[Accountability]:
        result = await self._session.execute(
            select(Accountability).where(
                Accountability.user_id == user_id, Accountability.rescue_candidate.is_(True)
            )
        )
        return list(result.scalars().all())

    async def find_by_state(
        self, *, user_id: int, state: AccountabilityState
    ) -> list[Accountability]:
        result = await self._session.execute(
            select(Accountability)
            .where(Accountability.user_id == user_id, Accountability.state == state)
            .order_by(Accountability.updated_at.desc())
        )
        return list(result.scalars().all())

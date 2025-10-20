import asyncio
import json
import os
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from .models import Base, User, Channel, Report, UserSettings


class Database:
    def __init__(self, dsn: str, echo: bool = False):
        self.engine = create_async_engine(dsn, echo=echo, future=True)
        self.SessionLocal = async_sessionmaker(self.engine, expire_on_commit=False, class_=AsyncSession)

    async def init_models(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self):
        await self.engine.dispose()

    @asynccontextmanager
    async def session(self) -> AsyncSession:
        async with self.SessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()


async def get_or_create_user(db: Database, user_id: int, username: Optional[str], first_name: Optional[str], admin_ids: List[int]) -> User:
    async with db.session() as session:
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(id=user_id, username=username, first_name=first_name, is_admin=(user_id in admin_ids))
            session.add(user)
            await session.commit()
            await session.refresh(user)
        else:
            # update last active and username
            user.last_active = user.last_active  # placeholder; SQLAlchemy tracks changes automatically
            if username and user.username != username:
                user.username = username
            if first_name and user.first_name != first_name:
                user.first_name = first_name
            await session.commit()
        return user


async def set_channel(db: Database, user_id: int, channel_id: str, channel_username: Optional[str]) -> Channel:
    async with db.session() as session:
        # ensure user exists
        result = await session.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(id=user_id)
            session.add(user)
            await session.flush()
        # deactivate previous channels
        await session.execute(update(Channel).where(Channel.user_id == user_id).values(is_active=False))
        # add new active channel
        channel = Channel(user_id=user_id, channel_id=str(channel_id), channel_username=channel_username, is_active=True)
        session.add(channel)
        await session.commit()
        await session.refresh(channel)
        return channel


async def get_active_channel(db: Database, user_id: int) -> Optional[Channel]:
    async with db.session() as session:
        result = await session.execute(
            select(Channel).where(Channel.user_id == user_id, Channel.is_active == True).order_by(Channel.added_at.desc())
        )
        return result.scalar_one_or_none()


async def get_user_settings(db: Database, user_id: int) -> UserSettings:
    async with db.session() as session:
        result = await session.execute(select(UserSettings).where(UserSettings.user_id == user_id))
        settings = result.scalar_one_or_none()
        if settings is None:
            settings = UserSettings(
                user_id=user_id,
                report_format="pdf",
                analysis_days=7,
                sources={"reddit": True, "freelance": True, "trends": True},
                include_charts=True,
                language="en",
            )
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings


async def save_report(
    db: Database,
    user_id: int,
    channel_id: Optional[int],
    file_path: str,
    fmt: str,
    data_json: Optional[Dict[str, Any]],
    status: str = "completed",
) -> Report:
    async with db.session() as session:
        report = Report(
            user_id=user_id,
            channel_id=channel_id,
            file_path=file_path,
            format=fmt,
            data_json=data_json,
            status=status,
        )
        session.add(report)
        await session.commit()
        await session.refresh(report)
        return report

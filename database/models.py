from __future__ import annotations

import datetime as dt
from typing import Optional

from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Text,
    JSON,
)
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)  # Telegram user_id
    username = Column(String(255), nullable=True)
    first_name = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    last_active = Column(DateTime, default=dt.datetime.utcnow)

    channels = relationship("Channel", back_populates="user", cascade="all, delete-orphan")
    schedules = relationship("Schedule", back_populates="user", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="user", cascade="all, delete-orphan")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(String(64), nullable=False)  # can hold numeric ID or @username
    channel_username = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    added_at = Column(DateTime, default=dt.datetime.utcnow)

    user = relationship("User", back_populates="channels")
    schedules = relationship("Schedule", back_populates="channel")
    reports = relationship("Report", back_populates="channel")


class Schedule(Base):
    __tablename__ = "schedules"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
    cron_expression = Column(String(255), nullable=False)
    timezone = Column(String(64), default="UTC")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)

    user = relationship("User", back_populates="schedules")
    channel = relationship("Channel", back_populates="schedules")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    channel_id = Column(Integer, ForeignKey("channels.id", ondelete="SET NULL"), nullable=True)
    file_path = Column(String(1024), nullable=False)
    format = Column(String(32), default="pdf")
    data_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    status = Column(String(32), default="pending")  # pending/completed/failed

    user = relationship("User", back_populates="reports")
    channel = relationship("Channel", back_populates="reports")


class UserSettings(Base):
    __tablename__ = "user_settings"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    report_format = Column(String(16), default="pdf")  # pdf/excel/html
    analysis_days = Column(Integer, default=7)
    sources = Column(JSON, default={"reddit": True, "freelance": True, "trends": True})
    include_charts = Column(Boolean, default=True)
    language = Column(String(8), default="en")

    user = relationship("User", back_populates="settings")

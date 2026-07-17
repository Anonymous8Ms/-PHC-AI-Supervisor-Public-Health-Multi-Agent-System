"""SQLAlchemy ORM models for the PHC AI Supervisor database schema."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, relationship

from database import Base


class PHC(Base):
    """Primary Health Centre location and metadata."""

    __tablename__ = "phcs"

    id: Mapped[int] = Column(Integer, primary_key=True)
    name: Mapped[str] = Column(String(100), nullable=False, index=True)
    district: Mapped[str] = Column(String(100), nullable=False, index=True)
    state: Mapped[str] = Column(String(100), nullable=False, index=True)
    lat: Mapped[float] = Column(Float, nullable=False)
    lng: Mapped[float] = Column(Float, nullable=False)

    health_workers: Mapped[List["HealthWorker"]] = relationship(
        "HealthWorker", back_populates="phc", cascade="all, delete-orphan"
    )
    households: Mapped[List["Household"]] = relationship(
        "Household", back_populates="phc", cascade="all, delete-orphan"
    )


class HealthWorker(Base):
    """Health worker profile and assignment details."""

    __tablename__ = "health_workers"

    id: Mapped[int] = Column(Integer, primary_key=True)
    name: Mapped[str] = Column(String(100), nullable=False, index=True)
    phone: Mapped[Optional[str]] = Column(String(20))
    zone: Mapped[str] = Column(String(100), nullable=False, index=True)
    phc_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("phcs.id"), index=True)
    language: Mapped[str] = Column(String(20), default="hindi", index=True)
    created_at: Mapped[Optional[datetime]] = Column(DateTime, default=datetime.utcnow, index=True)

    phc: Mapped[Optional["PHC"]] = relationship("PHC", back_populates="health_workers")
    visits: Mapped[List["Visit"]] = relationship("Visit", back_populates="worker", cascade="all, delete-orphan")


class Household(Base):
    """Household location and risk assessment data."""

    __tablename__ = "households"

    id: Mapped[int] = Column(Integer, primary_key=True)
    address: Mapped[str] = Column(String(255), nullable=False)
    zone: Mapped[str] = Column(String(100), nullable=False, index=True)
    lat: Mapped[float] = Column(Float, nullable=False)
    lng: Mapped[float] = Column(Float, nullable=False)
    phc_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("phcs.id"), index=True)
    risk_level: Mapped[str] = Column(String(20), default="normal", index=True)
    last_visit_date: Mapped[Optional[datetime]] = Column(DateTime, nullable=True, index=True)

    phc: Mapped[Optional["PHC"]] = relationship("PHC", back_populates="households")
    visits: Mapped[List["Visit"]] = relationship("Visit", back_populates="household", cascade="all, delete-orphan")


class Visit(Base):
    """Field visit report submitted by health workers."""

    __tablename__ = "visits"

    id: Mapped[int] = Column(Integer, primary_key=True)
    worker_id: Mapped[int] = Column(Integer, ForeignKey("health_workers.id"), index=True)
    household_id: Mapped[int] = Column(Integer, ForeignKey("households.id"), index=True)
    visit_date: Mapped[datetime] = Column(DateTime, nullable=False, index=True)
    gps_lat: Mapped[float] = Column(Float, nullable=False)
    gps_lng: Mapped[float] = Column(Float, nullable=False)
    photo_hash: Mapped[Optional[str]] = Column(String(64), nullable=True, index=True)
    reported_symptoms: Mapped[Optional[str]] = Column(Text, nullable=True)
    status: Mapped[str] = Column(String(20), default="pending", index=True)
    verification_reason: Mapped[Optional[str]] = Column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = Column(DateTime, default=datetime.utcnow, index=True)

    worker: Mapped[Optional["HealthWorker"]] = relationship("HealthWorker", back_populates="visits")
    household: Mapped[Optional["Household"]] = relationship("Household", back_populates="visits")
    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="visit", cascade="all, delete-orphan")


class Alert(Base):
    """System-generated alert for flagged visits or at-risk zones."""

    __tablename__ = "alerts"

    id: Mapped[int] = Column(Integer, primary_key=True)
    visit_id: Mapped[Optional[int]] = Column(Integer, ForeignKey("visits.id"), nullable=True, index=True)
    alert_type: Mapped[str] = Column(String(50), nullable=False, index=True)
    severity: Mapped[str] = Column(String(20), default="medium", index=True)
    message: Mapped[str] = Column(Text, nullable=False)
    zone: Mapped[str] = Column(String(100), nullable=False, index=True)
    is_resolved: Mapped[bool] = Column(Boolean, default=False, index=True)
    created_at: Mapped[Optional[datetime]] = Column(DateTime, default=datetime.utcnow, index=True)

    visit: Mapped[Optional["Visit"]] = relationship("Visit", back_populates="alerts")


class ChatLog(Base):
    """Supervisor chat interaction log."""

    __tablename__ = "chat_logs"

    id: Mapped[int] = Column(Integer, primary_key=True)
    user_query: Mapped[str] = Column(Text, nullable=False)
    agent_response: Mapped[str] = Column(Text, nullable=False)
    agent_name: Mapped[str] = Column(String(50), default="supervisor", index=True)
    created_at: Mapped[Optional[datetime]] = Column(DateTime, default=datetime.utcnow, index=True)

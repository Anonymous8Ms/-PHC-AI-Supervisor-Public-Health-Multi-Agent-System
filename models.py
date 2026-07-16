from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


class PHC(Base):
    __tablename__ = "phcs"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    district = Column(String(100), nullable=False, index=True)
    state = Column(String(100), nullable=False, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)

    health_workers = relationship("HealthWorker", back_populates="phc", cascade="all, delete-orphan")
    households = relationship("Household", back_populates="phc", cascade="all, delete-orphan")


class HealthWorker(Base):
    __tablename__ = "health_workers"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, index=True)
    phone = Column(String(20))
    zone = Column(String(100), nullable=False, index=True)
    phc_id = Column(Integer, ForeignKey("phcs.id"), index=True)
    language = Column(String(20), default="hindi", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    phc = relationship("PHC", back_populates="health_workers")
    visits = relationship("Visit", back_populates="worker", cascade="all, delete-orphan")


class Household(Base):
    __tablename__ = "households"

    id = Column(Integer, primary_key=True)
    address = Column(String(255), nullable=False)
    zone = Column(String(100), nullable=False, index=True)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    phc_id = Column(Integer, ForeignKey("phcs.id"), index=True)
    risk_level = Column(String(20), default="normal", index=True)
    last_visit_date = Column(DateTime, nullable=True, index=True)

    phc = relationship("PHC", back_populates="households")
    visits = relationship("Visit", back_populates="household", cascade="all, delete-orphan")


class Visit(Base):
    __tablename__ = "visits"

    id = Column(Integer, primary_key=True)
    worker_id = Column(Integer, ForeignKey("health_workers.id"), index=True)
    household_id = Column(Integer, ForeignKey("households.id"), index=True)
    visit_date = Column(DateTime, nullable=False, index=True)
    gps_lat = Column(Float, nullable=False)
    gps_lng = Column(Float, nullable=False)
    photo_hash = Column(String(64), nullable=True, index=True)
    reported_symptoms = Column(Text, nullable=True)
    status = Column(String(20), default="pending", index=True)
    verification_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    worker = relationship("HealthWorker", back_populates="visits")
    household = relationship("Household", back_populates="visits")
    alerts = relationship("Alert", back_populates="visit", cascade="all, delete-orphan")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=True, index=True)
    alert_type = Column(String(50), nullable=False, index=True)
    severity = Column(String(20), default="medium", index=True)
    message = Column(Text, nullable=False)
    zone = Column(String(100), nullable=False, index=True)
    is_resolved = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    visit = relationship("Visit", back_populates="alerts")


class ChatLog(Base):
    __tablename__ = "chat_logs"

    id = Column(Integer, primary_key=True)
    user_query = Column(Text, nullable=False)
    agent_response = Column(Text, nullable=False)
    agent_name = Column(String(50), default="supervisor", index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

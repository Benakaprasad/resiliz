"""
ResiliZ Database Layer
SQLAlchemy models and session engine supporting PostgreSQL with automatic SQLite fallback.
"""

import os
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, Integer, Float, String, Boolean, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./resiliz.db")

# Automatically configure appropriate connect_args for SQLite
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class TelemetryRecord(Base):
    __tablename__ = "telemetry_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    grid_id = Column(String(64), index=True)
    bus_id = Column(Integer, default=14, index=True)
    tick = Column(Integer)
    voltage_v = Column(Float)
    va = Column(Float, default=230.0)
    vb = Column(Float, default=230.0)
    vc = Column(Float, default=230.0)
    current_a = Column(Float)
    thd_pct = Column(Float, default=1.8)
    frequency_hz = Column(Float)
    active_power_kw = Column(Float)
    diffpriv_power_kw = Column(Float, default=25.0)
    reactive_power_kvar = Column(Float)
    power_factor = Column(Float)
    solar_pv_kw = Column(Float)
    battery_soc_pct = Column(Float)
    battery_power_kw = Column(Float)
    grid_connected = Column(Boolean, default=True)
    ground_truth_label = Column(String(64), default="NORMAL")


class AnomalyAlert(Base):
    __tablename__ = "anomaly_alerts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    grid_id = Column(String(64), index=True)
    tick = Column(Integer)
    severity = Column(String(32), index=True)  # NORMAL, ADVISORY, WARNING, CRITICAL
    classification = Column(String(64))
    anomaly_score = Column(Float)
    is_persistent = Column(Boolean)
    is_transient_filtered = Column(Boolean)
    explanations_json = Column(Text)
    contributing_features_json = Column(Text)
    audit_hash = Column(String(64), index=True)


class SystemAuditLog(Base):
    __tablename__ = "system_audit_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    event_type = Column(String(64), index=True)
    actor = Column(String(64))
    details_json = Column(Text)
    prev_hash = Column(String(64))
    record_hash = Column(String(64), unique=True)


class BenchmarkRun(Base):
    __tablename__ = "benchmark_runs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    total_samples = Column(Integer)
    results_json = Column(Text)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


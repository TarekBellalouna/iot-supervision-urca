from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- Modèles ORM PostgreSQL ---

class NodeDB(Base):
    __tablename__ = "nodes"

    node_id = Column(String(64), primary_key=True, index=True)
    network = Column(String(32), nullable=False)          # lorawan | zigbee | thread
    native_id = Column(String(128), nullable=False)       # DevEUI | IEEE 64-bit | IPv6 ML-EID
    role = Column(String(32), default="Sensor")
    ipv6_address = Column(String(64), nullable=True)
    expected_interval_s = Column(Integer, default=20)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(16), default="offline")        # online | delayed | lost | offline
    temperature_c = Column(Float, nullable=True)
    humidity_pct = Column(Float, nullable=True)
    pressure_hpa = Column(Float, nullable=True)
    battery_pct = Column(Integer, nullable=True)
    rssi_dbm = Column(Integer, nullable=True)
    snr_db = Column(Float, nullable=True)
    link_quality = Column(Integer, nullable=True)
    extra_meta = Column(JSON, default=dict)


class MeasurementDB(Base):
    __tablename__ = "measurements"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(128), unique=True, index=True, nullable=False)
    node_id = Column(String(64), index=True, nullable=False)
    network = Column(String(32), nullable=False)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    temperature_c = Column(Float, nullable=False)
    humidity_pct = Column(Float, nullable=False)
    pressure_hpa = Column(Float, nullable=False)
    battery_pct = Column(Integer, nullable=False)
    rssi_dbm = Column(Integer, nullable=True)
    snr_db = Column(Float, nullable=True)


class RejectedLogDB(Base):
    __tablename__ = "rejected_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    node_id = Column(String(64), nullable=False)
    network = Column(String(32), nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    reason = Column(String(255), nullable=False)
    raw_payload = Column(Text, nullable=True)


class QueryRecordDB(Base):
    __tablename__ = "queries"

    query_id = Column(String(64), primary_key=True, index=True)
    node_id = Column(String(64), nullable=False)
    network = Column(String(32), nullable=False)
    status = Column(String(24), nullable=False)           # sent | pending | succeeded | expired
    detail = Column(String(255), default="")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class PlatformCountersDB(Base):
    __tablename__ = "platform_counters"

    id = Column(Integer, primary_key=True, default=1)
    received_count = Column(Integer, default=0, nullable=False)
    rejected_count = Column(Integer, default=0, nullable=False)
    deduplicated_count = Column(Integer, default=0, nullable=False)


# --- Schémas Pydantic API / SSE ---

class NormalizedTelemetry(BaseModel):
    event_id: str
    network: str
    node_id: str
    native_id: str
    timestamp: datetime
    temperature_c: float
    humidity_pct: float
    pressure_hpa: float
    battery_pct: int
    rssi_dbm: Optional[int] = None
    snr_db: Optional[float] = None
    link_quality: Optional[int] = None
    role: str = "Sensor"
    ipv6_address: Optional[str] = None
    extra_meta: dict[str, Any] = {}
    is_query_response: bool = False


class NodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    node_id: str
    network: str
    native_id: str
    role: str
    ipv6_address: Optional[str]
    expected_interval_s: int
    last_seen: Optional[datetime]
    age_seconds: Optional[float] = None
    status: str
    temperature_c: Optional[float]
    humidity_pct: Optional[float]
    pressure_hpa: Optional[float]
    battery_pct: Optional[int]
    rssi_dbm: Optional[int]
    snr_db: Optional[float]
    link_quality: Optional[int]
    extra_meta: dict[str, Any]


class CountersOut(BaseModel):
    received_count: int
    rejected_count: int
    deduplicated_count: int


class QueryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    query_id: str
    node_id: str
    network: str
    status: str
    detail: str
    created_at: datetime
    updated_at: datetime
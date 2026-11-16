import asyncio
from datetime import datetime, timezone
import json
from typing import List
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.models import (
    CountersOut,
    MeasurementDB,
    NodeDB,
    NodeOut,
    PlatformCountersDB,
    QueryOut,
    QueryRecordDB,
    RejectedLogDB,
    SessionLocal,
)
from app.query_engine import query_engine

router = APIRouter(prefix="/api")

# Liste des files d'abonnement SSE actives
sse_subscribers: set[asyncio.Queue] = set()
main_event_loop: asyncio.AbstractEventLoop | None = None


def broadcast_sse(event_type: str, payload: dict):
    """Pousse un événement temps réel à tous les navigateurs connectés."""
    if not main_event_loop:
        return
    message = f"event: {event_type}\ndata: {json.dumps(payload)}\n\n"
    for q in list(sse_subscribers):
        main_event_loop.call_soon_threadsafe(q.put_nowait, message)


def _compute_node_age_and_status(node: NodeDB, now: datetime) -> NodeOut:
    out = NodeOut.model_validate(node)
    if node.last_seen:
        last_seen_utc = node.last_seen if node.last_seen.tzinfo else node.last_seen.replace(tzinfo=timezone.utc)
        age = max(0.0, (now - last_seen_utc).total_seconds())
        out.age_seconds = round(age, 1)
        interval = node.expected_interval_s or 20
        if age <= interval * 1.5:
            out.status = "online"
        elif age <= interval * 3.0:
            out.status = "delayed"
        else:
            out.status = "lost"
    else:
        out.age_seconds = None
        out.status = "offline"
    return out


@router.get("/nodes", response_model=List[NodeOut])
def list_nodes():
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        nodes = db.query(NodeDB).order_by(NodeDB.network, NodeDB.node_id).all()
        return [_compute_node_age_and_status(n, now) for n in nodes]
    finally:
        db.close()


@router.get("/nodes/{node_id}/history")
def get_node_history(node_id: str, limit: int = 40):
    db = SessionLocal()
    try:
        rows = (
            db.query(MeasurementDB)
            .filter(MeasurementDB.node_id == node_id)
            .order_by(MeasurementDB.timestamp.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return [
            {
                "timestamp": r.timestamp.isoformat(),
                "temperature_c": r.temperature_c,
                "humidity_pct": r.humidity_pct,
                "pressure_hpa": r.pressure_hpa,
                "battery_pct": r.battery_pct,
                "rssi_dbm": r.rssi_dbm,
                "snr_db": r.snr_db,
            }
            for r in rows
        ]
    finally:
        db.close()


@router.get("/counters", response_model=CountersOut)
def get_counters():
    db = SessionLocal()
    try:
        c = db.query(PlatformCountersDB).filter(PlatformCountersDB.id == 1).first()
        if not c:
            return CountersOut(received_count=0, rejected_count=0, deduplicated_count=0)
        return CountersOut(
            received_count=c.received_count,
            rejected_count=c.rejected_count,
            deduplicated_count=c.deduplicated_count,
        )
    finally:
        db.close()


@router.get("/rejections")
def get_recent_rejections(limit: int = 15):
    db = SessionLocal()
    try:
        logs = db.query(RejectedLogDB).order_by(RejectedLogDB.timestamp.desc()).limit(limit).all()
        return [
            {
                "id": l.id,
                "node_id": l.node_id,
                "network": l.network,
                "timestamp": l.timestamp.isoformat(),
                "reason": l.reason,
            }
            for l in logs
        ]
    finally:
        db.close()


@router.post("/nodes/{node_id}/query", response_model=QueryOut)
async def query_node(node_id: str):
    db = SessionLocal()
    try:
        node = db.query(NodeDB).filter(NodeDB.node_id == node_id).first()
        if not node:
            raise HTTPException(status_code=404, detail=f"Nœud {node_id} introuvable")
        # Détacher les attributs nécessaires avant de fermer la session
        node_copy = NodeDB(
            node_id=node.node_id,
            network=node.network,
            native_id=node.native_id,
            ipv6_address=node.ipv6_address,
        )
    finally:
        db.close()

    return await query_engine.start_query(node_copy)


@router.get("/queries", response_model=List[QueryOut])
def list_recent_queries(limit: int = 20):
    db = SessionLocal()
    try:
        recs = db.query(QueryRecordDB).order_by(QueryRecordDB.created_at.desc()).limit(limit).all()
        return [QueryOut.model_validate(r) for r in recs]
    finally:
        db.close()


@router.get("/stream")
async def sse_stream(request: Request):
    queue: asyncio.Queue = asyncio.Queue()
    sse_subscribers.add(queue)

    async def event_generator():
        try:
            yield "event: connected\ndata: {\"status\": \"ok\"}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield msg
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            sse_subscribers.discard(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
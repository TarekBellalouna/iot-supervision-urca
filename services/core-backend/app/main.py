import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app import routes
from app.models import Base, NodeDB, SessionLocal, engine
from app.mqtt_ingestor import ingestor
from app.query_engine import query_engine


async def health_monitor_loop():
    """Surveille périodiquement l'âge des mesures et met à jour l'état (online / delayed / lost)."""
    while True:
        await asyncio.sleep(3)
        db = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            nodes = db.query(NodeDB).all()
            changed = False
            for n in nodes:
                if not n.last_seen:
                    continue
                computed = routes._compute_node_age_and_status(n, now)
                if computed.status != n.status:
                    n.status = computed.status
                    changed = True
                    ingestor.publish(f"iot/v1/{n.network}/{n.node_id}/status", n.status)
                routes.broadcast_sse("node_update", computed.model_dump(mode="json"))
            if changed:
                db.commit()
        except Exception as exc:
            print(f"[Health Monitor] Erreur : {exc}")
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Création des tables PostgreSQL au démarrage
    Base.metadata.create_all(bind=engine)

    loop = asyncio.get_running_loop()
    routes.main_event_loop = loop

    ingestor.load_initial_topology()
    ingestor.set_sse_broadcaster(routes.broadcast_sse)

    query_engine.bind(
        loop=loop,
        mqtt_publish_fn=ingestor.publish,
        ingest_thread_payload_fn=ingestor.ingest_direct_thread_payload,
        broadcast_sse_fn=routes.broadcast_sse,
        lorawan_app_id=ingestor.lorawan_app_id,
    )

    ingestor.start()
    monitor_task = asyncio.create_task(health_monitor_loop())
    print("[Core Backend] Plateforme IoT démarrée et prête.")

    yield

    monitor_task.cancel()
    ingestor.stop()


app = FastAPI(title="URCA Multi-Network IoT Supervision Platform", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
import asyncio
from datetime import datetime, timezone
import json
import uuid
import aiocoap
from app.config import settings
from app.models import NodeDB, QueryOut, QueryRecordDB, SessionLocal


class QueryEngine:
    def __init__(self):
        self._pending_events: dict[str, list[asyncio.Event]] = {}
        self._mqtt_publish_fn = None
        self._ingest_thread_payload_fn = None
        self._broadcast_sse_fn = None
        self._lorawan_app_id: str = ""
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind(self, loop, mqtt_publish_fn, ingest_thread_payload_fn, broadcast_sse_fn, lorawan_app_id: str):
        self._loop = loop
        self._mqtt_publish_fn = mqtt_publish_fn
        self._ingest_thread_payload_fn = ingest_thread_payload_fn
        self._broadcast_sse_fn = broadcast_sse_fn
        self._lorawan_app_id = lorawan_app_id

    def _update_query_state(self, query_id: str, status: str, detail: str) -> QueryOut | None:
        db = SessionLocal()
        try:
            rec = db.query(QueryRecordDB).filter(QueryRecordDB.query_id == query_id).first()
            if not rec:
                return None
            rec.status = status
            rec.detail = detail
            rec.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(rec)
            out = QueryOut.model_validate(rec)
            if self._broadcast_sse_fn:
                self._broadcast_sse_fn("query_update", out.model_dump(mode="json"))
            return out
        finally:
            db.close()

    def notify_node_activity(self, node_id: str):
        """Réveille les interrogations en attente lorsqu'une réponse ou un uplink arrive."""
        if not self._loop:
            return
        events = self._pending_events.get(node_id, [])
        for ev in events:
            self._loop.call_soon_threadsafe(ev.set)

    async def start_query(self, node: NodeDB) -> QueryOut:
        query_id = str(uuid.uuid4())[:8]
        timeout_s = settings.QUERY_TIMEOUTS.get(node.network, 15)

        db = SessionLocal()
        try:
            rec = QueryRecordDB(
                query_id=query_id,
                node_id=node.node_id,
                network=node.network,
                status="sent",
                detail=f"Requête envoyée ({node.network.upper()}, timeout {timeout_s}s)",
            )
            db.add(rec)
            db.commit()
            db.refresh(rec)
            initial_out = QueryOut.model_validate(rec)
        finally:
            db.close()

        if self._broadcast_sse_fn:
            self._broadcast_sse_fn("query_update", initial_out.model_dump(mode="json"))

        asyncio.create_task(self._execute_query_workflow(query_id, node, timeout_s))
        return initial_out

    async def _execute_query_workflow(self, query_id: str, node: NodeDB, timeout_s: int):
        await asyncio.sleep(0.15)  # Laisse l'état "sent" (envoyée) visible brièvement

        if node.network == "thread":
            await self._query_thread_coap(query_id, node, timeout_s)
        elif node.network == "zigbee":
            await self._query_zigbee_mqtt(query_id, node, timeout_s)
        elif node.network == "lorawan":
            await self._query_lorawan_downlink(query_id, node, timeout_s)
        else:
            self._update_query_state(query_id, "expired", f"Réseau non supporté : {node.network}")

    async def _query_thread_coap(self, query_id: str, node: NodeDB, timeout_s: int):
        target_ip = node.ipv6_address or node.native_id
        uri = f"coap://[{target_ip}]:5683/sensor"
        self._update_query_state(query_id, "pending", f"GET {uri} en cours...")

        try:
            ctx = await aiocoap.Context.create_client_context()
            request = aiocoap.Message(code=aiocoap.Code.GET, uri=uri)
            response = await asyncio.wait_for(ctx.request(request).response, timeout=timeout_s)
            await ctx.shutdown()

            if response.code.is_successful():
                payload = json.loads(response.payload.decode("utf-8"))
                if self._ingest_thread_payload_fn:
                    self._ingest_thread_payload_fn(payload, is_query=True)
                self._update_query_state(query_id, "succeeded", f"Réponse CoAP 2.05 reçue de [{target_ip}]")
            else:
                self._update_query_state(query_id, "expired", f"Nœud indisponible (code CoAP {response.code})")
        except asyncio.TimeoutError:
            self._update_query_state(query_id, "expired", f"Délai expiré ({timeout_s}s) : nœud Thread endormi ou arrêté")
        except Exception as exc:
            self._update_query_state(query_id, "expired", f"Erreur CoAP IPv6 : {exc}")

    async def _query_zigbee_mqtt(self, query_id: str, node: NodeDB, timeout_s: int):
        ev = asyncio.Event()
        self._pending_events.setdefault(node.node_id, []).append(ev)
        self._update_query_state(query_id, "pending", f"Lecture ZCL envoyée sur zigbee2mqtt/{node.node_id}/get")

        if self._mqtt_publish_fn:
            self._mqtt_publish_fn(f"zigbee2mqtt/{node.node_id}/get", json.dumps({"state": ""}))

        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout_s)
            self._update_query_state(query_id, "succeeded", "Attributs ZCL lus avec succès")
        except asyncio.TimeoutError:
            self._update_query_state(query_id, "expired", f"Délai expiré ({timeout_s}s) : objet Zigbee en sommeil ou hors ligne")
        finally:
            self._pending_events[node.node_id].remove(ev)

    async def _query_lorawan_downlink(self, query_id: str, node: NodeDB, timeout_s: int):
        if not self._lorawan_app_id:
            self._update_query_state(query_id, "expired", "Application ID ChirpStack introuvable")
            return

        ev = asyncio.Event()
        self._pending_events.setdefault(node.node_id, []).append(ev)

        topic = f"application/{self._lorawan_app_id}/device/{node.native_id}/command/down"
        downlink_cmd = {
            "devEui": node.native_id,
            "confirmed": False,
            "fPort": 10,
            "data": "AQ==",  # Commande applicative 0x01 (demande de mesure immédiate)
        }
        if self._mqtt_publish_fn:
            self._mqtt_publish_fn(topic, json.dumps(downlink_cmd))

        self._update_query_state(
            query_id,
            "pending",
            "Downlink en file ChirpStack — livraison prévue à la prochaine fenêtre RX1/RX2",
        )

        try:
            await asyncio.wait_for(ev.wait(), timeout=timeout_s)
            self._update_query_state(query_id, "succeeded", "Downlink délivré et mesure montante reçue")
        except asyncio.TimeoutError:
            self._update_query_state(query_id, "expired", f"Délai expiré ({timeout_s}s) : aucun uplink reçu")
        finally:
            self._pending_events[node.node_id].remove(ev)


query_engine = QueryEngine()
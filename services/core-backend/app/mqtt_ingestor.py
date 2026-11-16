from datetime import datetime, timezone
import json
import os
import threading
import uuid
import paho.mqtt.client as mqtt
from app.config import settings
from app.deduplicator import deduplicator
from app.models import (
    CountersOut,
    MeasurementDB,
    NodeDB,
    NodeOut,
    PlatformCountersDB,
    RejectedLogDB,
    SessionLocal,
)
from app.models import NormalizedTelemetry
from app.query_engine import query_engine
from app.validator import validate_telemetry


class MqttIngestor:
    def __init__(self):
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="urca-core-backend")
        self._db_lock = threading.Lock()
        self._broadcast_sse_fn = None
        self.lorawan_app_id: str = ""
        self.lorawan_map_by_eui: dict[str, str] = {}

    def set_sse_broadcaster(self, fn):
        self._broadcast_sse_fn = fn

    def load_initial_topology(self):
        """Pré-enregistre les nœuds des 3 réseaux en base pour garantir une supervision dès le démarrage."""
        db = SessionLocal()
        try:
            if not db.query(PlatformCountersDB).filter(PlatformCountersDB.id == 1).first():
                db.add(PlatformCountersDB(id=1, received_count=0, rejected_count=0, deduplicated_count=0))

            # 1. Chargement des nœuds LoRaWAN générés par le provisioner
            lora_file = os.path.join(settings.SHARED_DIR, "lorawan_devices.json")
            if os.path.exists(lora_file):
                with open(lora_file, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                self.lorawan_app_id = cfg.get("application_id", "")
                for n in cfg.get("nodes", []):
                    self.lorawan_map_by_eui[n["dev_eui"].lower()] = n["node_id"]
                    self._ensure_node(
                        db,
                        node_id=n["node_id"],
                        network="lorawan",
                        native_id=n["dev_eui"].lower(),
                        role="Class A",
                        expected_interval_s=settings.EXPECTED_INTERVALS["lorawan"],
                    )

            # 2. Nœuds Zigbee
            zigbee_defs = [
                ("zb-node-01", "00:15:8d:00:01:a2:b3:01", "Router"),
                ("zb-node-02", "00:15:8d:00:01:a2:b3:02", "Router"),
                ("zb-node-03", "00:15:8d:00:01:a2:b3:03", "EndDevice (Sleepy)"),
            ]
            for nid, ieee, role in zigbee_defs:
                self._ensure_node(db, nid, "zigbee", ieee, role, settings.EXPECTED_INTERVALS["zigbee"])

            # 3. Nœuds Thread IPv6
            prefix = settings.THREAD_IPV6_PREFIX
            thread_defs = [
                ("th-node-01", f"{prefix}11", "Leader"),
                ("th-node-02", f"{prefix}12", "Router"),
                ("th-node-03", f"{prefix}13", "FED"),
                ("th-node-04", f"{prefix}14", "SED (Sleepy)"),
            ]
            for nid, ipv6, role in thread_defs:
                self._ensure_node(
                    db, nid, "thread", ipv6, role, settings.EXPECTED_INTERVALS["thread"], ipv6_address=ipv6
                )

            db.commit()
        finally:
            db.close()

    def _ensure_node(
        self,
        db,
        node_id: str,
        network: str,
        native_id: str,
        role: str,
        expected_interval_s: int,
        ipv6_address: str | None = None,
    ):
        existing = db.query(NodeDB).filter(NodeDB.node_id == node_id).first()
        if not existing:
            db.add(
                NodeDB(
                    node_id=node_id,
                    network=network,
                    native_id=native_id,
                    role=role,
                    ipv6_address=ipv6_address,
                    expected_interval_s=expected_interval_s,
                    status="offline",
                )
            )

    def start(self):
        self.client.username_pw_set(settings.MQTT_USER, settings.MQTT_PASSWORD)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.reconnect_delay_set(min_delay=1, max_delay=10)
        self.client.connect_async(settings.MQTT_HOST, settings.MQTT_PORT, keepalive=30)
        self.client.loop_start()

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def publish(self, topic: str, payload: str):
        self.client.publish(topic, payload, qos=1)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        print(f"[Core MQTT] Connecté au broker Mosquitto ({reason_code})")
        client.subscribe("application/+/device/+/event/up", qos=1)
        client.subscribe("zigbee2mqtt/+", qos=1)
        client.subscribe("iot/v1/thread/+/telemetry", qos=1)

    def _on_message(self, client, userdata, msg):
        try:
            raw_str = msg.payload.decode("utf-8")
            data = json.loads(raw_str)
            topic = msg.topic

            if topic.startswith("application/") and topic.endswith("/event/up"):
                item = self._parse_lorawan(data)
            elif topic.startswith("zigbee2mqtt/"):
                if topic.endswith("/get") or topic.endswith("/set") or "bridge" in topic:
                    return
                node_id = topic.split("/")[1]
                item = self._parse_zigbee(node_id, data)
            elif topic.startswith("iot/v1/thread/") and topic.endswith("/telemetry"):
                item = self._parse_thread(data)
            else:
                return

            if item:
                self.process_telemetry(item, raw_str)
        except Exception as exc:
            print(f"[Core MQTT] Erreur décodage message sur {msg.topic} : {exc}")

    def _parse_lorawan(self, data: dict) -> NormalizedTelemetry | None:
        dev_info = data.get("deviceInfo", {})
        dev_eui = dev_info.get("devEui", "").lower()
        node_id = self.lorawan_map_by_eui.get(dev_eui) or dev_info.get("deviceName") or f"lora-{dev_eui[-4:]}"
        fcnt = data.get("fCnt", 0)
        obj = data.get("object", {})
        if not obj:
            return None

        rx_list = data.get("rxInfo", [])
        best_rx = max(rx_list, key=lambda r: r.get("rssi", -150)) if rx_list else {}
        tx_info = data.get("txInfo", {})
        sf = tx_info.get("modulation", {}).get("lora", {}).get("spreadingFactor", 7)

        return NormalizedTelemetry(
            event_id=f"lorawan:{dev_eui}:fcnt-{fcnt}",
            network="lorawan",
            node_id=node_id,
            native_id=dev_eui,
            timestamp=datetime.now(timezone.utc),
            temperature_c=float(obj.get("temperature_c")),
            humidity_pct=float(obj.get("humidity_pct")),
            pressure_hpa=float(obj.get("pressure_hpa")),
            battery_pct=int(obj.get("battery_pct")),
            rssi_dbm=best_rx.get("rssi"),
            snr_db=best_rx.get("snr"),
            role="Class A",
            extra_meta={
                "frame_counter": fcnt,
                "spreading_factor": sf,
                "gateways_count": len(rx_list),
                "best_gateway": best_rx.get("gatewayId"),
            },
        )

    def _parse_zigbee(self, node_id: str, data: dict) -> NormalizedTelemetry | None:
        ieee = data.get("ieee_address", node_id)
        nwk = data.get("network_address", "0x0000")
        is_query = bool(data.get("query_response", False))
        # Utilise un ID déterministe basé sur les valeurs et la tranche temporelle de 1s pour capter les doublons MQTT
        ts_sec = int(datetime.now(timezone.utc).timestamp())
        event_id = f"zigbee:{ieee}:{ts_sec}:{data.get('temperature')}:{data.get('humidity')}"

        return NormalizedTelemetry(
            event_id=event_id,
            network="zigbee",
            node_id=node_id,
            native_id=ieee,
            timestamp=datetime.now(timezone.utc),
            temperature_c=float(data.get("temperature")),
            humidity_pct=float(data.get("humidity")),
            pressure_hpa=float(data.get("pressure")),
            battery_pct=int(data.get("battery")),
            link_quality=data.get("linkquality"),
            role=data.get("role", "Router"),
            extra_meta={
                "network_address": nwk,
                "pan_id": data.get("pan_id", "0x1A62"),
                "zcl_clusters": list(data.get("zcl_clusters", {}).keys()),
            },
            is_query_response=is_query,
        )

    def _parse_thread(self, data: dict, is_query: bool = False) -> NormalizedTelemetry | None:
        node_id = data.get("node_id")
        ipv6 = data.get("ipv6_address")
        meas = data.get("measurements", {})
        ts_sec = int(datetime.now(timezone.utc).timestamp())
        event_id = f"thread:{node_id}:{uuid.uuid4().hex[:8]}" if is_query else f"thread:{node_id}:{ts_sec}:{meas.get('temperature_c')}"

        return NormalizedTelemetry(
            event_id=event_id,
            network="thread",
            node_id=node_id,
            native_id=ipv6,
            timestamp=datetime.now(timezone.utc),
            temperature_c=float(meas.get("temperature_c")),
            humidity_pct=float(meas.get("humidity_pct")),
            pressure_hpa=float(meas.get("pressure_hpa")),
            battery_pct=int(meas.get("battery_pct")),
            rssi_dbm=data.get("rssi_dbm"),
            snr_db=data.get("snr_db"),
            role=data.get("thread_role", "Router"),
            ipv6_address=ipv6,
            extra_meta={"rloc16": data.get("rloc16")},
            is_query_response=is_query or bool(data.get("is_query_response", False)),
        )

    def ingest_direct_thread_payload(self, data: dict, is_query: bool = True):
        item = self._parse_thread(data, is_query=is_query)
        if item:
            self.process_telemetry(item, json.dumps(data))

    def process_telemetry(self, item: NormalizedTelemetry, raw_payload: str):
        with self._db_lock:
            db = SessionLocal()
            try:
                counters = db.query(PlatformCountersDB).filter(PlatformCountersDB.id == 1).first()

                # 1. Dédoublonnage
                if deduplicator.is_duplicate(item):
                    counters.deduplicated_count += 1
                    db.commit()
                    self._emit_counters(counters)
                    print(f"[Core] Doublon écarté : {item.event_id}")
                    return

                # 2. Validation des plages physiques
                is_valid, reason = validate_telemetry(item)
                if not is_valid:
                    counters.rejected_count += 1
                    db.add(
                        RejectedLogDB(
                            node_id=item.node_id,
                            network=item.network,
                            reason=reason,
                            raw_payload=raw_payload[:1000],
                        )
                    )
                    db.commit()
                    self._emit_counters(counters)
                    if self._broadcast_sse_fn:
                        self._broadcast_sse_fn(
                            "rejection_alert",
                            {"node_id": item.node_id, "network": item.network, "reason": reason},
                        )
                    print(f"[Core][REJET] {item.node_id} : {reason}")
                    return

                # 3. Persistance de la mesure valide et mise à jour du nœud
                counters.received_count += 1
                db.add(
                    MeasurementDB(
                        event_id=item.event_id,
                        node_id=item.node_id,
                        network=item.network,
                        timestamp=item.timestamp,
                        temperature_c=item.temperature_c,
                        humidity_pct=item.humidity_pct,
                        pressure_hpa=item.pressure_hpa,
                        battery_pct=item.battery_pct,
                        rssi_dbm=item.rssi_dbm,
                        snr_db=item.snr_db,
                    )
                )

                node = db.query(NodeDB).filter(NodeDB.node_id == item.node_id).first()
                if not node:
                    node = NodeDB(
                        node_id=item.node_id,
                        network=item.network,
                        native_id=item.native_id,
                        expected_interval_s=settings.EXPECTED_INTERVALS.get(item.network, 20),
                    )
                    db.add(node)

                node.native_id = item.native_id
                node.role = item.role
                node.ipv6_address = item.ipv6_address
                node.last_seen = item.timestamp
                node.status = "online"
                node.temperature_c = item.temperature_c
                node.humidity_pct = item.humidity_pct
                node.pressure_hpa = item.pressure_hpa
                node.battery_pct = item.battery_pct
                node.rssi_dbm = item.rssi_dbm
                node.snr_db = item.snr_db
                node.link_quality = item.link_quality
                node.extra_meta = item.extra_meta

                db.commit()
                db.refresh(node)

                # Republie sur le topic unifié de la plateforme
                self.publish(
                    f"iot/v1/{item.network}/{item.node_id}/telemetry",
                    item.model_dump_json(),
                )

                # Débloque d'éventuelles requêtes en attente sur ce nœud (LoRaWAN / Zigbee)
                query_engine.notify_node_activity(item.node_id)

                # Diffusion temps réel vers le Dashboard
                self._emit_counters(counters)
                if self._broadcast_sse_fn:
                    node_out = NodeOut.model_validate(node)
                    node_out.age_seconds = 0.0
                    self._broadcast_sse_fn("node_update", node_out.model_dump(mode="json"))

            finally:
                db.close()

    def _emit_counters(self, counters: PlatformCountersDB):
        if self._broadcast_sse_fn:
            c_out = CountersOut(
                received_count=counters.received_count,
                rejected_count=counters.rejected_count,
                deduplicated_count=counters.deduplicated_count,
            )
            self._broadcast_sse_fn("counters_update", c_out.model_dump(mode="json"))


ingestor = MqttIngestor()
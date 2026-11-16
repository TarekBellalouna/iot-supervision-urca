import asyncio
import json
import os
import subprocess
import threading
import time
import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException
import uvicorn
from coap_node import build_thread_payload, start_coap_server

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "thread_bridge")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
IPV6_PREFIX = os.getenv("IPV6_PREFIX", "fd00:db8:1::")
CONTROL_PORT = int(os.getenv("CONTROL_PORT", "8093"))

app = FastAPI(title="Thread Mesh & CoAP Control API")

THREAD_NODES = {
    "th-node-01": {"node_id": "th-node-01", "ipv6": f"{IPV6_PREFIX}11", "role": "Leader", "rloc16": "0x0400", "sleepy": False, "is_awake": True, "active": True, "battery": 100},
    "th-node-02": {"node_id": "th-node-02", "ipv6": f"{IPV6_PREFIX}12", "role": "Router", "rloc16": "0x0800", "sleepy": False, "is_awake": True, "active": True, "battery": 100},
    "th-node-03": {"node_id": "th-node-03", "ipv6": f"{IPV6_PREFIX}13", "role": "FED", "rloc16": "0x0801", "sleepy": False, "is_awake": True, "active": True, "battery": 95},
    "th-node-04": {"node_id": "th-node-04", "ipv6": f"{IPV6_PREFIX}14", "role": "SED", "rloc16": "0x0802", "sleepy": True, "is_awake": True, "active": True, "battery": 88},
}

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="thread-border-router-sim")


def find_ipv6_interface(prefix: str) -> str:
    """Détecte dynamiquement l'interface réseau (eth0 ou eth1) attachée au réseau IPv6 Thread."""
    res = subprocess.run(["ip", "-6", "-o", "addr", "show"], capture_output=True, text=True, check=False)
    for line in res.stdout.splitlines():
        if prefix in line:
            parts = line.split()
            if len(parts) >= 2:
                return parts[1]
    return "eth1"


def configure_ipv6_aliases():
    """Attache les adresses IPv6 stables ML-EID des nœuds Thread sur l'interface IPv6."""
    iface = find_ipv6_interface(IPV6_PREFIX)
    print(f"[Thread] Configuration des alias IPv6 sur l'interface {iface}...")
    for node in THREAD_NODES.values():
        cmd = ["ip", "-6", "addr", "add", f"{node['ipv6']}/64", "dev", iface, "nodad"]
        subprocess.run(cmd, check=False)
    time.sleep(0.5)


def publish_telemetry(node: dict, force_invalid: bool = False):
    payload = build_thread_payload(node, force_invalid=force_invalid, is_query=False)
    topic = f"iot/v1/thread/{node['node_id']}/telemetry"
    mqtt_client.publish(topic, json.dumps(payload), qos=1)
    print(f"[Thread] {node['node_id']} [{node['ipv6']}] -> T={payload['measurements']['temperature_c']}°C")


async def mesh_loop():
    for node in THREAD_NODES.values():
        await start_coap_server(node)

    tick = 0
    while True:
        for node in THREAD_NODES.values():
            if not node["active"]:
                continue
            if node["sleepy"]:
                # SED : éveillé 10s toutes les 30s
                node["is_awake"] = (tick % 3 == 0)
                if node["is_awake"]:
                    publish_telemetry(node)
            else:
                node["is_awake"] = True
                publish_telemetry(node)
        tick += 1
        await asyncio.sleep(10)


@app.post("/control/{node_id}/stop")
def stop_node(node_id: str):
    if node_id not in THREAD_NODES:
        raise HTTPException(404, "Nœud inconnu")
    THREAD_NODES[node_id]["active"] = False
    return {"status": "stopped", "node_id": node_id}


@app.post("/control/{node_id}/start")
def start_node(node_id: str):
    if node_id not in THREAD_NODES:
        raise HTTPException(404, "Nœud inconnu")
    THREAD_NODES[node_id]["active"] = True
    return {"status": "started", "node_id": node_id}


@app.post("/control/{node_id}/invalid")
def invalid_node(node_id: str):
    if node_id not in THREAD_NODES:
        raise HTTPException(404, "Nœud inconnu")
    publish_telemetry(THREAD_NODES[node_id], force_invalid=True)
    return {"status": "invalid_sent", "node_id": node_id}


def start_async_mesh():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(mesh_loop())


if __name__ == "__main__":
    configure_ipv6_aliases()
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    mqtt_client.loop_start()

    threading.Thread(target=start_async_mesh, daemon=True).start()
    uvicorn.run(app, host="0.0.0.0", port=CONTROL_PORT)
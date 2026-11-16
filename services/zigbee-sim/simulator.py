import json
import os
import threading
import time
import paho.mqtt.client as mqtt
from fastapi import FastAPI, HTTPException
import uvicorn
from zcl_model import ZigbeeNode

MQTT_HOST = os.getenv("MQTT_HOST", "mosquitto")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "zigbee_coord")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
CONTROL_PORT = int(os.getenv("CONTROL_PORT", "8092"))

app = FastAPI(title="Zigbee Simulator Control API")

ZIGBEE_NODES = {
    "zb-node-01": ZigbeeNode("zb-node-01", "00:15:8d:00:01:a2:b3:01", "0x1001", role="Router", sleepy=False),
    "zb-node-02": ZigbeeNode("zb-node-02", "00:15:8d:00:01:a2:b3:02", "0x1002", role="Router", sleepy=False),
    "zb-node-03": ZigbeeNode("zb-node-03", "00:15:8d:00:01:a2:b3:03", "0x1003", role="EndDevice", sleepy=True),
}

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="zigbee-coordinator-sim")


def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[Zigbee Coord] Connecté au broker MQTT ({reason_code})")
    client.publish("zigbee2mqtt/bridge/state", "online", qos=1, retain=True)
    client.subscribe("zigbee2mqtt/+/get", qos=1)


def on_message(client, userdata, msg):
    parts = msg.topic.split("/")
    if len(parts) == 3 and parts[2] == "get":
        node_id = parts[1]
        node = ZIGBEE_NODES.get(node_id)
        if not node or not node.active:
            print(f"[Zigbee Coord] Échec lecture ZCL : {node_id} hors ligne.")
            return
        if not node.is_awake:
            print(f"[Zigbee Coord] Échec lecture ZCL : {node_id} est en sommeil profond (End Device).")
            return

        payload = node.read_zcl_clusters()
        payload["query_response"] = True
        client.publish(f"zigbee2mqtt/{node_id}", json.dumps(payload), qos=1)
        print(f"[Zigbee Coord] Lecture ZCL réussie sur {node_id} ({node.nwk_addr})")


def publish_telemetry(node: ZigbeeNode, force_invalid: bool = False):
    payload = node.read_zcl_clusters(force_invalid=force_invalid)
    payload["query_response"] = False
    mqtt_client.publish(f"zigbee2mqtt/{node.node_id}", json.dumps(payload), qos=1)
    print(f"[Zigbee] {node.node_id} ({node.ieee_addr}) -> T={payload['temperature']}°C")


def node_worker(node: ZigbeeNode):
    while True:
        if node.active:
            if node.sleepy:
                # Cycle End Device : 5s éveillé (émission + écoute), 25s sommeil profond
                node.is_awake = True
                publish_telemetry(node)
                time.sleep(5)
                node.is_awake = False
                time.sleep(25)
            else:
                node.is_awake = True
                publish_telemetry(node)
                time.sleep(15)
        else:
            time.sleep(2)


@app.post("/control/{node_id}/stop")
def stop_node(node_id: str):
    if node_id not in ZIGBEE_NODES:
        raise HTTPException(404, "Nœud inconnu")
    ZIGBEE_NODES[node_id].active = False
    return {"status": "stopped", "node_id": node_id}


@app.post("/control/{node_id}/start")
def start_node(node_id: str):
    if node_id not in ZIGBEE_NODES:
        raise HTTPException(404, "Nœud inconnu")
    ZIGBEE_NODES[node_id].active = True
    return {"status": "started", "node_id": node_id}


@app.post("/control/{node_id}/invalid")
def invalid_node(node_id: str):
    if node_id not in ZIGBEE_NODES:
        raise HTTPException(404, "Nœud inconnu")
    publish_telemetry(ZIGBEE_NODES[node_id], force_invalid=True)
    return {"status": "invalid_sent", "node_id": node_id}


@app.post("/control/{node_id}/sleep")
def force_sleep(node_id: str):
    if node_id not in ZIGBEE_NODES:
        raise HTTPException(404, "Nœud inconnu")
    ZIGBEE_NODES[node_id].is_awake = False
    return {"status": "sleeping", "node_id": node_id}


def bootstrap():
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    mqtt_client.will_set("zigbee2mqtt/bridge/state", "offline", qos=1, retain=True)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
    mqtt_client.loop_start()

    for node in ZIGBEE_NODES.values():
        threading.Thread(target=node_worker, args=(node,), daemon=True).start()


if __name__ == "__main__":
    bootstrap()
    uvicorn.run(app, host="0.0.0.0", port=CONTROL_PORT)
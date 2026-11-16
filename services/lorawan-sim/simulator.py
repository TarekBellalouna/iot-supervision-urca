import json
import os
import random
import threading
import time
from fastapi import FastAPI, HTTPException
import uvicorn
from gateway import SemtechGateway
from lorawan_crypto import build_uplink_phy_payload

SHARED_DIR = os.getenv("SHARED_DIR", "/shared")
BRIDGE_HOST = os.getenv("GATEWAY_BRIDGE_HOST", "chirpstack-gateway-bridge")
BRIDGE_PORT = int(os.getenv("GATEWAY_BRIDGE_PORT", "1700"))
CONTROL_PORT = int(os.getenv("CONTROL_PORT", "8091"))

app = FastAPI(title="LoRaWAN Simulator Control API")
NODES_STATE = {}
GATEWAYS = []


def handle_downlink(gw_name: str, phy_down: bytes):
    """Identifie le nœud destinataire d'un downlink Classe A et déclenche une réponse immédiate."""
    if len(phy_down) < 12:
        return
    dev_addr_le = phy_down[1:5]
    dev_addr_hex = dev_addr_le[::-1].hex()

    for node in NODES_STATE.values():
        if node["dev_addr"].lower() == dev_addr_hex.lower():
            print(f"[LoRaWAN] Downlink reçu via {gw_name} pour {node['node_id']} -> réponse dans l'uplink suivant.")
            node["pending_query_reply"] = True


def send_node_uplink(node: dict, replay_last: bool = False, force_invalid: bool = False):
    if replay_last and node.get("last_phy"):
        phy = node["last_phy"]
        print(f"[LoRaWAN][REJEU] Réémission d'une ancienne trame pour {node['node_id']} (FCnt figé)")
    else:
        temp = 125.5 if force_invalid else round(random.uniform(18.5, 24.5), 2)
        hum = round(random.uniform(40.0, 65.0), 2)
        press = round(random.uniform(1005.0, 1022.0), 1)
        batt = max(10, node["battery"])

        phy = build_uplink_phy_payload(
            dev_addr_hex=node["dev_addr"],
            nwk_s_key_hex=node["nwk_s_key"],
            app_s_key_hex=node["app_s_key"],
            fcnt=node["fcnt"],
            temp_c=temp,
            hum_pct=hum,
            press_hpa=press,
            batt_pct=batt,
        )
        node["last_phy"] = phy
        node["fcnt"] += 1
        print(f"[LoRaWAN] Uplink {node['node_id']} | FCnt={node['fcnt'] - 1} | T={temp}°C")

    # Les 2 passerelles à portée reçoivent la même trame radio (test dédoublonnage ChirpStack)
    for idx, gw in enumerate(GATEWAYS):
        rssi = random.randint(-95, -72) - (idx * 6)
        snr = round(random.uniform(4.5, 9.5) - (idx * 1.5), 1)
        gw.forward_uplink(phy, rssi=rssi, snr=snr, sf=7)


def node_loop(node_id: str):
    while True:
        node = NODES_STATE[node_id]
        if node["active"]:
            send_node_uplink(node)
            # Fenêtre RX1 (1s après l'uplink) : si un downlink est arrivé, le nœud répond vite
            time.sleep(1.5)
            if node.get("pending_query_reply"):
                node["pending_query_reply"] = False
                time.sleep(1.0)
                send_node_uplink(node)
        time.sleep(18.5)


@app.post("/control/{node_id}/stop")
def stop_node(node_id: str):
    if node_id not in NODES_STATE:
        raise HTTPException(404, "Nœud inconnu")
    NODES_STATE[node_id]["active"] = False
    return {"status": "stopped", "node_id": node_id}


@app.post("/control/{node_id}/start")
def start_node(node_id: str):
    if node_id not in NODES_STATE:
        raise HTTPException(404, "Nœud inconnu")
    NODES_STATE[node_id]["active"] = True
    return {"status": "started", "node_id": node_id}


@app.post("/control/{node_id}/replay")
def replay_frame(node_id: str):
    if node_id not in NODES_STATE:
        raise HTTPException(404, "Nœud inconnu")
    send_node_uplink(NODES_STATE[node_id], replay_last=True)
    return {"status": "replayed", "node_id": node_id}


@app.post("/control/{node_id}/invalid")
def inject_invalid(node_id: str):
    if node_id not in NODES_STATE:
        raise HTTPException(404, "Nœud inconnu")
    send_node_uplink(NODES_STATE[node_id], force_invalid=True)
    return {"status": "invalid_sent", "node_id": node_id}


def bootstrap():
    config_file = os.path.join(SHARED_DIR, "lorawan_devices.json")
    while not os.path.exists(config_file):
        time.sleep(1)

    with open(config_file, "r", encoding="utf-8") as f:
        cfg = json.load(f)

    for gw_cfg in cfg["gateways"]:
        GATEWAYS.append(
            SemtechGateway(gw_cfg["id"], gw_cfg["name"], BRIDGE_HOST, BRIDGE_PORT, handle_downlink)
        )

    for n in cfg["nodes"]:
        NODES_STATE[n["node_id"]] = {
            **n,
            "fcnt": 0,
            "battery": random.randint(85, 100),
            "active": True,
            "last_phy": None,
            "pending_query_reply": False,
        }
        threading.Thread(target=node_loop, args=(n["node_id"],), daemon=True).start()


if __name__ == "__main__":
    bootstrap()
    uvicorn.run(app, host="0.0.0.0", port=CONTROL_PORT)
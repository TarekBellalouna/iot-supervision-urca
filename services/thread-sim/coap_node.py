import asyncio
import json
import random
import aiocoap
import aiocoap.resource as resource


class SensorResource(resource.Resource):
    """Ressource CoAP GET /sensor exposée sur l'adresse IPv6 stable du nœud Thread."""

    def __init__(self, node_state: dict):
        super().__init__()
        self.node_state = node_state

    async def render_get(self, request):
        if not self.node_state["active"] or not self.node_state["is_awake"]:
            # Un nœud éteint ou en veille (SED) ne renvoie pas d'ACK CoAP -> Timeout côté client
            await asyncio.sleep(10)
            return aiocoap.Message(code=aiocoap.Code.SERVICE_UNAVAILABLE)

        payload = build_thread_payload(self.node_state, is_query=True)
        return aiocoap.Message(
            code=aiocoap.Code.CONTENT,
            content_format=50,  # application/json
            payload=json.dumps(payload).encode("utf-8"),
        )


def build_thread_payload(node_state: dict, force_invalid: bool = False, is_query: bool = False) -> dict:
    temp = 92.4 if force_invalid else round(random.uniform(19.5, 23.8), 2)
    hum = round(random.uniform(42.0, 58.0), 2)
    press = round(random.uniform(1010.0, 1024.0), 1)

    return {
        "node_id": node_state["node_id"],
        "ipv6_address": node_state["ipv6"],
        "thread_role": node_state["role"],
        "rloc16": node_state["rloc16"],
        "rssi_dbm": random.randint(-68, -45),
        "snr_db": round(random.uniform(8.0, 14.0), 1),
        "measurements": {
            "temperature_c": temp,
            "humidity_pct": hum,
            "pressure_hpa": press,
            "battery_pct": node_state["battery"],
        },
        "is_query_response": is_query,
    }


async def start_coap_server(node_state: dict):
    root = resource.Site()
    root.add_resource([".well-known", "core"], resource.WKCResource(root.get_resources_as_linkheader))
    root.add_resource(["sensor"], SensorResource(node_state))

    await aiocoap.Context.create_server_context(root, bind=(node_state["ipv6"], 5683))
    print(f"[Thread CoAP] Nœud {node_state['node_id']} ({node_state['role']}) en écoute sur coap://[{node_state['ipv6']}]:5683/sensor")
import base64
import json
import os
import socket
import threading
import time


class SemtechGateway:
    """Passerelle LoRaWAN simulée communiquant en UDP Semtech avec ChirpStack Gateway Bridge."""

    def __init__(self, gw_id_hex: str, name: str, bridge_host: str, bridge_port: int, on_downlink_cb):
        self.gw_id_hex = gw_id_hex
        self.gw_eui = bytes.fromhex(gw_id_hex)
        self.name = name
        self.bridge_addr = (bridge_host, bridge_port)
        self.on_downlink_cb = on_downlink_cb
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(1.0)
        self.running = True
        self._start_threads()

    def _start_threads(self):
        threading.Thread(target=self._pull_loop, daemon=True).start()
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def _pull_loop(self):
        """Envoie périodiquement PULL_DATA pour maintenir le canal descendant actif."""
        while self.running:
            pkt = b"\x02" + os.urandom(2) + b"\x02" + self.gw_eui
            try:
                self.sock.sendto(pkt, self.bridge_addr)
            except OSError:
                pass
            time.sleep(10)

    def _recv_loop(self):
        """Écoute les acquittements et les messages descendants PULL_RESP."""
        while self.running:
            try:
                data, _ = self.sock.recvfrom(4096)
                if len(data) >= 4 and data[3] == 0x03:  # PULL_RESP
                    token = data[1:3]
                    # Acquitter par TX_ACK (0x05)
                    ack = b"\x02" + token + b"\x05" + self.gw_eui + b'{"txpk_ack":{"error":"NONE"}}'
                    self.sock.sendto(ack, self.bridge_addr)

                    payload_json = json.loads(data[4:].decode("utf-8"))
                    txpk = payload_json.get("txpk", {})
                    if "data" in txpk:
                        phy_down = base64.b64decode(txpk["data"])
                        self.on_downlink_cb(self.name, phy_down)
            except socket.timeout:
                continue
            except Exception as exc:
                print(f"[Gateway {self.name}] Erreur réception UDP : {exc}")

    def forward_uplink(self, phy_payload: bytes, rssi: int, snr: float, sf: int = 7):
        """Transmet une trame radio reçue vers le Gateway Bridge via PUSH_DATA."""
        rxpk = {
            "rxpk": [
                {
                    "tmst": int(time.monotonic() * 1_000_000) & 0xFFFFFFFF,
                    "chan": 0,
                    "rfch": 0,
                    "freq": 868.1,
                    "stat": 1,
                    "modu": "LORA",
                    "datr": f"SF{sf}BW125",
                    "codr": "4/5",
                    "lsnr": round(snr, 1),
                    "rssi": rssi,
                    "size": len(phy_payload),
                    "data": base64.b64encode(phy_payload).decode("ascii"),
                }
            ]
        }
        pkt = b"\x02" + os.urandom(2) + b"\x00" + self.gw_eui + json.dumps(rxpk).encode("utf-8")
        self.sock.sendto(pkt, self.bridge_addr)
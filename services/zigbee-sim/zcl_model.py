from dataclasses import dataclass, field
import random


@dataclass
class ZigbeeNode:
    node_id: str
    ieee_addr: str          # Adresse IEEE 64 bits fixe
    nwk_addr: str           # Adresse réseau 16 bits (PAN ID 0x1A62)
    role: str               # "Router" ou "EndDevice"
    sleepy: bool = False    # True pour un objet sur pile en veille périodique
    is_awake: bool = True
    active: bool = True
    battery_pct: int = field(default_factory=lambda: random.randint(80, 100))

    def read_zcl_clusters(self, force_invalid: bool = False) -> dict:
        """
        Lit les attributs ZCL sur l'Endpoint 1 :
        - 0x0402 (Temperature Measurement) / Attr 0x0000 (int16 °C * 100)
        - 0x0405 (Relative Humidity)       / Attr 0x0000 (uint16 % * 100)
        - 0x0403 (Pressure Measurement)    / Attr 0x0000 (int16 hPa)
        - 0x0001 (Power Configuration)     / Attr 0x0021 (uint8 %)
        """
        temp = -85.0 if force_invalid else round(random.uniform(19.0, 25.0), 2)
        hum = round(random.uniform(38.0, 62.0), 2)
        press = round(random.uniform(1008.0, 1020.0), 1)

        return {
            "ieee_address": self.ieee_addr,
            "network_address": self.nwk_addr,
            "pan_id": "0x1A62",
            "endpoint": 1,
            "role": self.role,
            "linkquality": random.randint(140, 255),
            "zcl_clusters": {
                "0x0402": {"0x0000": int(round(temp * 100))},
                "0x0405": {"0x0000": int(round(hum * 100))},
                "0x0403": {"0x0000": int(round(press))},
                "0x0001": {"0x0021": self.battery_pct},
            },
            "temperature": temp,
            "humidity": hum,
            "pressure": press,
            "battery": self.battery_pct,
        }
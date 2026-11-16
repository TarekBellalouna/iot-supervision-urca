import os


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://iot_user:iot_db_urca_2026_secret@postgres:5432/iot_platform"
    )
    MQTT_HOST: str = os.getenv("MQTT_HOST", "mosquitto")
    MQTT_PORT: int = int(os.getenv("MQTT_PORT", "1883"))
    MQTT_USER: str = os.getenv("MQTT_USER", "core_backend")
    MQTT_PASSWORD: str = os.getenv("MQTT_PASSWORD", "")
    SHARED_DIR: str = os.getenv("SHARED_DIR", "/shared")
    THREAD_IPV6_PREFIX: str = os.getenv("THREAD_IPV6_PREFIX", "fd00:db8:1::")

    # Délais d'expiration adaptés aux contraintes radio de chaque réseau (en secondes)
    QUERY_TIMEOUTS: dict[str, int] = {
        "thread": 5,     # Requête directe CoAP UDP/IPv6
        "zigbee": 8,     # Lecture d'attribut ZCL via coordinateur MQTT
        "lorawan": 90,   # Attente du prochain uplink Classe A (fenêtres RX1/RX2)
    }

    # Période d'émission nominale par réseau pour détecter le retard ou la perte (en secondes)
    EXPECTED_INTERVALS: dict[str, int] = {
        "thread": 10,
        "zigbee": 15,
        "lorawan": 20,
    }


settings = Settings()
from collections import OrderedDict
import hashlib
import threading
import time
from app.models import NormalizedTelemetry


class Deduplicator:
    def __init__(self, max_entries: int = 5000, window_seconds: float = 2.0):
        self.max_entries = max_entries
        self.window_seconds = window_seconds
        self._seen_events: OrderedDict[str, float] = OrderedDict()
        self._seen_fingerprints: OrderedDict[str, float] = OrderedDict()
        self._lock = threading.Lock()

    def is_duplicate(self, item: NormalizedTelemetry) -> bool:
        now = time.monotonic()
        raw_fp = (
            f"{item.network}:{item.native_id}:{item.temperature_c}:"
            f"{item.humidity_pct}:{item.pressure_hpa}:{item.battery_pct}"
        )
        fp_hash = hashlib.sha256(raw_fp.encode("utf-8")).hexdigest()[:24]

        with self._lock:
            # 1. Vérification par identifiant d'événement (ex: lorawan:DevEUI:fcnt-X)
            if item.event_id in self._seen_events:
                return True

            # 2. Vérification par empreinte de mesure dans une fenêtre de 2 secondes
            prev_ts = self._seen_fingerprints.get(fp_hash)
            if prev_ts is not None and (now - prev_ts) < self.window_seconds:
                return True

            self._seen_events[item.event_id] = now
            self._seen_fingerprints[fp_hash] = now

            while len(self._seen_events) > self.max_entries:
                self._seen_events.popitem(last=False)
            while len(self._seen_fingerprints) > self.max_entries:
                self._seen_fingerprints.popitem(last=False)

            return False


deduplicator = Deduplicator()
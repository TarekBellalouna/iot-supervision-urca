from typing import Tuple
from app.models import NormalizedTelemetry

VALID_RANGES = {
    "temperature_c": (-40.0, 60.0, "°C"),
    "humidity_pct": (0.0, 100.0, "%"),
    "pressure_hpa": (900.0, 1100.0, "hPa"),
    "battery_pct": (0, 100, "%"),
}


def validate_telemetry(data: NormalizedTelemetry) -> Tuple[bool, str]:
    """Vérifie que toutes les grandeurs mesurées respectent les plages physiques autorisées."""
    values = {
        "temperature_c": data.temperature_c,
        "humidity_pct": data.humidity_pct,
        "pressure_hpa": data.pressure_hpa,
        "battery_pct": data.battery_pct,
    }

    for field_name, (min_val, max_val, unit) in VALID_RANGES.items():
        val = values.get(field_name)
        if val is None:
            return False, f"Champ manquant : {field_name}"
        if not (min_val <= val <= max_val):
            return False, f"{field_name} hors plage ({val} {unit}, attendu [{min_val}, {max_val}])"

    return True, "OK"
import json
from datetime import datetime, date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TARIFF_FILE = BASE_DIR / "kenya_tariffs" / "kenya_electricity_tariffs.json"


def load_tariffs():
    with open(TARIFF_FILE, "r") as f:
        return json.load(f)


def parse_date(d):
    if not d:
        return None
    try:
        return datetime.strptime(d, "%Y-%m-%d").date()
    except:
        return None


def get_tariff_for_date(target_date: date):
    """
    Returns correct energy charge for a given date
    based on historical tariff structure.
    """
    data = load_tariffs()
    structures = data.get("historical_tariff_structures", [])

    for row in structures:
        start = parse_date(row.get("start_date"))
        end = parse_date(row.get("end_date"))

        if not start:
            continue

        if start <= target_date and (end is None or target_date <= end):
            energy = row.get("Energy_Charge_KES_kWh")

            if not energy:
                continue

            try:
                return float(energy)
            except:
                import re
                match = re.findall(r"(\d+\.\d+)", energy)
                if match:
                    return float(match[-1])

    # fallback safety value
    return 15.0


def calculate_kwh_cost(readings):
    """
    Reads DeviceData queryset and calculates exact cost
    using per-reading tariff matching.
    """
    total = 0.0

    for r in readings:
        rate = get_tariff_for_date(r.time.date())
        total += (r.kwh or 0) * rate

    return round(total, 2)
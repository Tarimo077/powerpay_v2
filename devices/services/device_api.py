import requests
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware, is_naive


def call_change_status_api(deviceid, desired_status):
    """
    Calls external API to change device status.

    Returns:
        {
            "success": bool,
            "status": bool,
            "updated_time": datetime or None,
            "error": str or None
        }
    """

    try:
        api_payload = {
            "selectedDev": deviceid,
            "status": desired_status
        }

        response = requests.post(
            "https://appliapay.com/changeStatus",
            json=api_payload,
            timeout=10
        )

        if response.status_code != 200:
            return {
                "success": False,
                "error": f"API error {response.status_code}"
            }

        data = response.json()

        new_status = data.get("status", desired_status)
        updated_time_str = data.get("time")

        updated_time = None
        if updated_time_str:
            dt = parse_datetime(updated_time_str)
            if dt:
                updated_time = make_aware(dt) if is_naive(dt) else dt

        return {
            "success": True,
            "status": new_status,
            "updated_time": updated_time,
            "error": None
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "error": str(e)
        }

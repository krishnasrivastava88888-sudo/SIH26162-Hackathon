import os
import json
import time
import requests
from dotenv import load_dotenv

load_dotenv()

CACHE_FILE_PATH = "cache/alert_cache.json"
ALERT_COOLDOWN_SECONDS = 7200  # 2 Hours


def _load_cache() -> dict:
    if os.path.exists(CACHE_FILE_PATH):
        try:
            with open(CACHE_FILE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_cache(cache_data: dict) -> None:
    os.makedirs(os.path.dirname(CACHE_FILE_PATH), exist_ok=True)
    with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache_data, f, indent=2)


def is_rate_limited(lat: float, lon: float) -> bool:
    """Checks whether an alert for this coordinate grid was already dispatched within 2 hours."""
    grid_hash = f"{round(lat, 2)}_{round(lon, 2)}"
    current_time = time.time()
    cache = _load_cache()

    last_sent = cache.get(grid_hash, 0)
    if current_time - last_sent < ALERT_COOLDOWN_SECONDS:
        return True

    cache[grid_hash] = current_time
    _save_cache(cache)
    return False


def send_discord_webhook(alert_data: dict) -> bool:
    """Dispatches a structured embed card to Discord."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url or not webhook_url.startswith("https://discord.com"):
        return False

    lat = alert_data["latitude"]
    lon = alert_data["longitude"]
    maps_url = f"https://www.google.com/maps?q={lat},{lon}"

    payload = {
        "username": "ThermoGuard AI Tactical Sentinel",
        "avatar_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/NASA_logo.svg/300px-NASA_logo.svg.png",
        "embeds": [
            {
                "title": "🚨 CRITICAL INDUSTRIAL THERMAL ANOMALY DETECTED",
                "description": f"A high-intensity thermal spike was detected near **{alert_data['nearest_facility']}** with zero prior baseline flaring history.",
                "url": maps_url,
                "color": 15158332,  # Crimson Red
                "fields": [
                    {"name": "Nearest Facility", "value": f"`{alert_data['nearest_facility']}` ({alert_data['distance_to_facility_km']} km)", "inline": True},
                    {"name": "Fire Radiative Power", "value": f"**{alert_data['frp']} MW**", "inline": True},
                    {"name": "Brightness Temp", "value": f"{alert_data['brightness_k']} K", "inline": True},
                    {"name": "Persistence (30d)", "value": f"{alert_data['persistence_count_30d']} active days", "inline": True},
                    {"name": "AI Confidence", "value": f"{int(alert_data['confidence_score'] * 100)}%", "inline": True},
                    {"name": "Satellite Instrument", "value": f"`{alert_data['satellite']}`", "inline": True},
                    {"name": "Coordinates", "value": f"[{lat}, {lon}]({maps_url})", "inline": False},
                    {"name": "Detection Time (IST)", "value": str(alert_data["acq_timestamp_ist"]), "inline": False}
                ],
                "footer": {
                    "text": "Smart India Hackathon • SIH26162 NTRO Operational Feed"
                },
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            }
        ]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        return response.status_code in [200, 204]
    except Exception as e:
        print(f"[Discord] Dispatch error: {e}")
        return False


def send_telegram_alert(alert_data: dict) -> bool:
    """Dispatches an HTML-formatted notification to Telegram."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        return False

    lat = alert_data["latitude"]
    lon = alert_data["longitude"]
    maps_url = f"https://www.google.com/maps?q={lat},{lon}"

    message_text = (
        "🚨 <b>CRITICAL INDUSTRIAL ACCIDENT DETECTED</b>\n\n"
        f"<b>Facility:</b> {alert_data['nearest_facility']}\n"
        f"<b>Distance:</b> {alert_data['distance_to_facility_km']} km\n"
        f"<b>FRP:</b> <code>{alert_data['frp']} MW</code>\n"
        f"<b>Brightness:</b> <code>{alert_data['brightness_k']} K</code>\n"
        f"<b>30-Day Recurrence:</b> {alert_data['persistence_count_30d']} days (Spontaneous Spike)\n"
        f"<b>Confidence:</b> {int(alert_data['confidence_score'] * 100)}%\n"
        f"<b>Satellite:</b> {alert_data['satellite']}\n"
        f"<b>Timestamp:</b> {alert_data['acq_timestamp_ist']}\n"
        f"<b>Location:</b> <a href=\"{maps_url}\">{lat}, {lon}</a>\n"
    )

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    try:
        response = requests.post(api_url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"[Telegram] Dispatch error: {e}")
        return False


def dispatch_critical_alert(alert_data: dict) -> None:
    """Validates anti-spam debounce cache and dispatches to configured webhook channels."""
    lat = alert_data["latitude"]
    lon = alert_data["longitude"]

    if is_rate_limited(lat, lon):
        print(f"[Rate-Limiter] Suppressed repeated alert for [{lat}, {lon}] (2-hour cooldown active).")
        return

    discord_ok = send_discord_webhook(alert_data)
    telegram_ok = send_telegram_alert(alert_data)

    status_flags = []
    if discord_ok:
        status_flags.append("Discord")
    if telegram_ok:
        status_flags.append("Telegram")

    if status_flags:
        print(f"[Notifier] Dispatched alerts via: {', '.join(status_flags)}")
    else:
        print("[Notifier] Alert evaluated, but no active Webhook URLs are configured in .env.")


if __name__ == "__main__":
    # Standalone mock test execution
    mock_payload = {
        "latitude": 26.8315,
        "longitude": 80.8872,
        "frp": 240.5,
        "brightness_k": 368.2,
        "satellite": "VIIRS_NOAA21_NRT",
        "acq_timestamp_ist": "2026-09-11 20:30:00 IST",
        "persistence_count_30d": 1,
        "nearest_facility": "Talkatora Industrial Estate",
        "distance_to_facility_km": 0.42,
        "classification": "CRITICAL_ACCIDENTAL",
        "severity": "CRITICAL",
        "confidence_score": 0.97
    }
    print("Testing dispatch logic...")
    dispatch_critical_alert(mock_payload)
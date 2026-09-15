import json
import os
import time
from dotenv import load_dotenv
import requests

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
  try:
    os.makedirs(os.path.dirname(CACHE_FILE_PATH), exist_ok=True)
    with open(CACHE_FILE_PATH, "w", encoding="utf-8") as f:
      json.dump(cache_data, f, indent=2)
  except Exception as e:
    print(f"[Cache Error]: {e}")


def is_rate_limited(lat: float, lon: float) -> bool:
  """Checks whether an alert for this coordinate grid was already dispatched within 2 hours."""
  grid_hash = f"{round(float(lat), 2)}_{round(float(lon), 2)}"
  current_time = time.time()
  cache = _load_cache()

  last_sent = cache.get(grid_hash, 0)
  if current_time - last_sent < ALERT_COOLDOWN_SECONDS:
    return True

  cache[grid_hash] = current_time
  _save_cache(cache)
  return False


def send_discord_webhook(alert_data: dict, max_retries: int = 3) -> bool:
  """Dispatches a structured embed card to Discord with custom User-Agent,

  progressive 429 backoff jitter, and spatial debounce deduplication.
  """
  webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
  if not webhook_url or not webhook_url.startswith("https://discord.com"):
    print("[Discord] DISCORD_WEBHOOK_URL is missing or invalid in .env")
    return False

  lat = alert_data.get("latitude", 26.8315)
  lon = alert_data.get("longitude", 80.8872)

  if not alert_data.get("force_alert", False) and is_rate_limited(lat, lon):
    print(
        f"[Discord] Suppressed duplicate alert for [{lat}, {lon}] (2-hour"
        " cooldown active)."
    )
    return False

  maps_url = f"https://www.google.com/maps?q={lat},{lon}"
  facility = alert_data.get("nearest_facility", "Talkatora Industrial Estate")
  dist_km = alert_data.get(
      "distance_to_facility_km", alert_data.get("distance_km", 0.10)
  )
  frp_val = alert_data.get(
      "frp", alert_data.get("fire_radiative_power", 350.0)
  )
  brightness = alert_data.get(
      "brightness_k", alert_data.get("brightness", 355.0)
  )
  persist_val = alert_data.get(
      "persistence_count_30d", alert_data.get("persistence_count", 1)
  )

  conf = alert_data.get(
      "confidence_score", alert_data.get("confidence", 0.95)
  )
  try:
    conf_pct = (
        int(float(conf) * 100) if float(conf) <= 1.0 else int(float(conf))
    )
  except Exception:
    conf_pct = 95

  sat_instrument = alert_data.get("satellite", "VIIRS_NOAA21_NRT")
  detection_time = alert_data.get(
      "acq_timestamp_ist", time.strftime("%Y-%m-%d %H:%M:%S IST")
  )

  payload = {
      "username": "ThermoGuard AI Tactical Sentinel",
      "avatar_url": (
          "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e5/NASA_logo.svg/300px-NASA_logo.svg.png"
      ),
      "embeds": [{
          "title": "🚨 CRITICAL INDUSTRIAL THERMAL ANOMALY DETECTED",
          "description": (
              "High-intensity thermal signature detected near"
              f" **{facility}** requiring tactical evaluation."
          ),
          "url": maps_url,
          "color": 15158332,
          "fields": [
              {
                  "name": "Nearest Facility",
                  "value": f"`{facility}` ({dist_km} km)",
                  "inline": True,
              },
              {
                  "name": "Fire Radiative Power",
                  "value": f"**{frp_val} MW**",
                  "inline": True,
              },
              {
                  "name": "Brightness Temp",
                  "value": f"{brightness} K",
                  "inline": True,
              },
              {
                  "name": "Persistence (30d)",
                  "value": f"{persist_val} active days",
                  "inline": True,
              },
              {
                  "name": "AI Confidence",
                  "value": f"{conf_pct}%",
                  "inline": True,
              },
              {
                  "name": "Satellite Instrument",
                  "value": f"`{sat_instrument}`",
                  "inline": True,
              },
              {
                  "name": "Coordinates",
                  "value": f"[{lat}, {lon}]({maps_url})",
                  "inline": False,
              },
              {
                  "name": "Detection Time (IST)",
                  "value": str(detection_time),
                  "inline": False,
              },
          ],
          "footer": {
              "text": "Smart India Hackathon • SIH26162 NTRO Operational Feed"
          },
          "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
      }],
  }

  headers = {
      "Content-Type": "application/json",
      "User-Agent": (
          "ThermoGuardAI-Sentinel/2.0 (SIH26162 NTRO Operational Feed)"
      ),
  }

  for attempt in range(1, max_retries + 1):
    try:
      response = requests.post(
          webhook_url, json=payload, headers=headers, timeout=10
      )
      if response.status_code in (200, 204):
        print(f"[Discord] Live dispatch successful for {facility}.")
        return True

      if response.status_code == 429:
        wait_time = 3.0
        try:
          data = response.json()
          wait_time = float(
              data.get("retry_after", response.headers.get("Retry-After", 3.0))
          )
        except Exception:
          pass
        wait_time = max(wait_time, 2.0) + (attempt * 1.5)
        print(
            f"[Discord] Rate limit reached (HTTP 429). Waiting {wait_time:.1f}s"
            f" (Attempt {attempt}/{max_retries})..."
        )
        time.sleep(wait_time)
        continue

      print(
          f"[Discord] Webhook rejected: HTTP {response.status_code} -"
          f" {response.text}"
      )
      return False
    except Exception as req_err:
      print(
          f"[Discord] Network error (Attempt {attempt}/{max_retries}): {req_err}"
      )
      time.sleep(1.5)

  return False


def send_telegram_alert(alert_data: dict) -> bool:
  """Dispatches an HTML-formatted notification to Telegram."""
  bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
  chat_id = os.getenv("TELEGRAM_CHAT_ID")
  if not bot_token or not chat_id:
    return False

  lat = alert_data.get("latitude", 26.8315)
  lon = alert_data.get("longitude", 80.8872)
  maps_url = f"https://www.google.com/maps?q={lat},{lon}"
  facility = alert_data.get("nearest_facility", "Talkatora Industrial Estate")
  dist = alert_data.get(
      "distance_to_facility_km", alert_data.get("distance_km", 0.10)
  )
  frp = alert_data.get("frp", alert_data.get("fire_radiative_power", 350.0))
  bright = alert_data.get("brightness_k", alert_data.get("brightness", 355.0))
  persist = alert_data.get(
      "persistence_count_30d", alert_data.get("persistence_count", 1)
  )

  conf = alert_data.get("confidence_score", alert_data.get("confidence", 0.95))
  try:
    conf_pct = (
        int(float(conf) * 100) if float(conf) <= 1.0 else int(float(conf))
    )
  except Exception:
    conf_pct = 95

  sat = alert_data.get("satellite", "VIIRS_NOAA21_NRT")
  ts = alert_data.get(
      "acq_timestamp_ist", time.strftime("%Y-%m-%d %H:%M:%S IST")
  )

  message_text = (
      "🚨 <b>CRITICAL INDUSTRIAL ACCIDENT DETECTED</b>\n\n"
      f"<b>Facility:</b> {facility}\n"
      f"<b>Distance:</b> {dist} km\n"
      f"<b>FRP:</b> <code>{frp} MW</code>\n"
      f"<b>Brightness:</b> <code>{bright} K</code>\n"
      f"<b>30-Day Recurrence:</b> {persist} days (Spontaneous Spike)\n"
      f"<b>Confidence:</b> {conf_pct}%\n"
      f"<b>Satellite:</b> {sat}\n"
      f"<b>Timestamp:</b> {ts}\n"
      f'<b>Location:</b> <a href="{maps_url}">{lat}, {lon}</a>\n'
  )

  api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
  payload = {
      "chat_id": chat_id,
      "text": message_text,
      "parse_mode": "HTML",
      "disable_web_page_preview": False,
  }

  try:
    response = requests.post(api_url, json=payload, timeout=10)
    return response.status_code == 200
  except Exception as e:
    print(f"[Telegram] Dispatch error: {e}")
    return False


def dispatch_critical_alert(alert_data: dict) -> None:
  """Validates debounce cache and dispatches to configured channels."""
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
    print(
        "[Notifier] Alert suppressed by cooldown or webhook channels"
        " unconfigured."
    )


if __name__ == "__main__":
  mock_payload = {
      "latitude": 26.8315,
      "longitude": 80.8872,
      "frp": 240.5,
      "brightness_k": 368.2,
      "satellite": "VIIRS_NOAA21_NRT",
      "acq_timestamp_ist": "2026-09-14 17:15:00 IST",
      "persistence_count_30d": 1,
      "nearest_facility": "Talkatora Industrial Estate",
      "distance_to_facility_km": 0.42,
      "force_alert": True,
  }
  print("Testing dispatch with 429 resiliency...")
  send_discord_webhook(mock_payload)
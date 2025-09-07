import os, json, urllib.request, urllib.error
from datetime import datetime, timezone
import boto3

s3 = boto3.client("s3")
secrets = boto3.client("secretsmanager")

BUCKET = os.environ["BUCKET"]
SECRET_NAME = os.environ.get("SECRET_NAME", "openweather/api")
BASE_PATH = os.environ.get("BASE_PATH", "raw")
CITIES = [c.strip() for c in os.environ.get("CITIES", "Riyadh").split(",") if c.strip()]

def _get_api_key():
    resp = secrets.get_secret_value(SecretId=SECRET_NAME)
    data = json.loads(resp["SecretString"])
    return data["OPENWEATHER_API_KEY"]

def _fetch_city_weather(city: str, api_key: str) -> dict:
    url = (
        "https://api.openweathermap.org/data/2.5/weather"
        f"?q={urllib.parse.quote(city)}&appid={api_key}&units=metric"
    )
    with urllib.request.urlopen(url, timeout=10) as r:
        payload = json.loads(r.read().decode("utf-8"))

    main = payload.get("weather", [{}])[0] or {}
    info = payload.get("main", {}) or {}
    wind = payload.get("wind", {}) or {}

    now = datetime.now(timezone.utc)
    return {
        "city_name": city,
        "ts_utc": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "weather_main": main.get("main"),
        "weather_desc": main.get("description"),
        "temp_c": info.get("temp"),
        "humidity": info.get("humidity"),
        "pressure_hpa": info.get("pressure"),
        "wind_speed_ms": wind.get("speed"),
        "raw": payload,
    }

def _s3_key_for(city: str, now: datetime) -> str:
    safe_city = city.replace(" ", "_")
    dt_str = now.strftime("%Y-%m-%d")
    hour_str = now.strftime("%H")
    ts = now.strftime("%Y%m%dT%H%M%SZ")
    return f"{BASE_PATH}/city={safe_city}/dt={dt_str}/hour={hour_str}/{ts}.json"

def lambda_handler(event, context):
    api_key = _get_api_key()
    results = []
    errors = []

    for city in CITIES:
        try:
            rec = _fetch_city_weather(city, api_key)
            now = datetime.now(timezone.utc)
            key = _s3_key_for(city, now)

            body = json.dumps(rec, separators=(",", ":")) + "\n"
            s3.put_object(
                Bucket=BUCKET,
                Key=key,
                Body=body.encode("utf-8"),
                ContentType="application/json",
            )

            results.append({"city": city, "s3_key": key})
        except urllib.error.HTTPError as e:
            errors.append({"city": city, "error": f"HTTP {e.code}: {e.reason}"})
        except Exception as e:
            errors.append({"city": city, "error": str(e)})

    return {
        "written": results,
        "errors": errors,
        "bucket": BUCKET,
        "count_success": len(results),
        "count_errors": len(errors),
    }

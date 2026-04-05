import os
import json
import pickle
import requests
import numpy as np
import time
import traceback
import google.auth

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
from scipy.spatial import KDTree
from google.oauth2 import service_account
from google.auth.transport.requests import Request

from auth import User
from bot import router as chat_router


# CONFIGURATION

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

MODEL_PATH = "flood_xgboost_model.pkl"
TERRAIN_PATH = "terrain_lookup.json"
COORDINATE_PATH = "indian_district_coordinates.json"


# LOAD MODEL

try:
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    print("XGBoost model loaded successfully")

except Exception as e:
    raise RuntimeError(f"Failed to load model: {e}")

# LOAD TERRAIN DATASET
with open("terrain_lookup.json", "r") as f:
    TERRAIN_DATA = json.load(f)

print("Terrain dataset loaded")

# Extract coordinates
terrain_coords = [(p["lat"], p["lon"]) for p in TERRAIN_DATA]

# Build KDTree
terrain_tree = KDTree(terrain_coords)

print("KDTree spatial index built")


# FASTAPI INITIALIZATION

user_handler = User()

app = FastAPI(title="Early Flood Predictor API", version="2.0")

app.include_router(chat_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# REQUEST MODELS

class FloodRequest(BaseModel):
    timestamp: float = 0


class SignupRequest(BaseModel):
    username: str
    password: str
    full_name: str = ""


class LoginRequest(BaseModel):
    username: str
    password: str


class CoordinateRequest(BaseModel):
    latitude: float
    longitude: float

# DISTRICT COORDINATES

def get_coordinates(state: str, district: str):

    with open(COORDINATE_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    state_key = next((s for s in data if s.lower() == state.lower()), None)

    if not state_key:
        raise HTTPException(status_code=404, detail=f"State '{state}' not found")

    district_key = next((d for d in data[state_key] if d.lower() == district.lower()), None)

    if not district_key:
        raise HTTPException(status_code=404, detail=f"District '{district}' not found")

    return data[state_key][district_key]


# WEATHER FETCH

weather_cache = {}

def get_weather(lat, lon):

    key = f"{round(lat,2)}_{round(lon,2)}"

    if key in weather_cache:

        cached, ts = weather_cache[key]

        if time.time() - ts < 600:
            return cached

    params = {
        "lat": lat,
        "lon": lon,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric"
    }

    resp = requests.get(
        "https://api.openweathermap.org/data/2.5/weather",
        params=params,
        timeout=10
    )

    resp.raise_for_status()

    data = resp.json()

    weather_cache[key] = (data, time.time())

    return data

#Openmeteo
def get_openmeteo_rainfall(lat, lon):
    from datetime import datetime, timedelta

    end = datetime.utcnow().date()
    start = end - timedelta(days=30)

    url = "https://archive-api.open-meteo.com/v1/archive"

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start.strftime("%Y-%m-%d"),
        "end_date": end.strftime("%Y-%m-%d"),
        "daily": "precipitation_sum",
        "timezone": "auto"
    }

    try:
        res = requests.get(url, params=params, timeout=10)
        data = res.json()

        values = data.get("daily", {}).get("precipitation_sum", [])

        values = [v for v in values if v is not None and v >= 0]

        values_60d = values[-60:] if len(values) >= 60 else values

        if len(values_60d) >= 60:
            previous_30d = sum(values_60d[:30])
            current_30d = sum(values_60d[30:])
        else:
            current_30d = sum(values_60d)
            previous_30d = current_30d * 0.8

        rain_7d = sum(values_60d[-7:]) if len(values_60d) >= 7 else current_30d
        rain_24h = values_60d[-2] if len(values_60d) > 1 else 0

        return rain_24h, rain_7d, current_30d, previous_30d, values_60d

    except Exception as e:
        print("Open-Meteo error:", e)
        return 0, 0

def get_forecast_data(lat, lon):
    url = "https://api.openweathermap.org/data/2.5/forecast"

    params = {
        "lat": lat,
        "lon": lon,
        "appid": OPENWEATHER_API_KEY,
        "units": "metric"
    }

    res = requests.get(url, params=params, timeout=10)
    data = res.json()

    return data["list"]

def process_forecast_daily(forecast_list):
    daily_data = {}

    for item in forecast_list:
        date = item["dt_txt"].split(" ")[0]

        rain = item.get("rain", {}).get("3h", 0)
        humidity = item["main"]["humidity"]
        temp = item["main"]["temp"]
        wind = item["wind"]["speed"]

        if date not in daily_data:
            daily_data[date] = {
                "rain_total": 0,
                "rain_max": 0,
                "humidity": [],
                "temp": [],
                "wind": []
            }

        daily_data[date]["rain_total"] += rain
        daily_data[date]["rain_max"] = max(daily_data[date]["rain_max"], rain)
        daily_data[date]["humidity"].append(humidity)
        daily_data[date]["temp"].append(temp)
        daily_data[date]["wind"].append(wind)

    result = []
    for date, d in daily_data.items():
        result.append({
            "date": date,
            "rain": d["rain_total"],
            "rain_max": d["rain_max"],
            "humidity": sum(d["humidity"]) / len(d["humidity"]),
            "temp": sum(d["temp"]) / len(d["temp"]),
            "wind": sum(d["wind"]) / len(d["wind"])
        })

    return result

# TERRAIN LOOKUP

def find_nearest_terrain(lat, lon):

    distance, index = terrain_tree.query((lat, lon))

    return TERRAIN_DATA[index]


# FEATURE GENERATION

def build_features(lat, lon, weather, rain_24h, rain_7d, current_30d, previous_30d):

    terrain = find_nearest_terrain(lat, lon)

    rainfall = current_30d

    wind = weather.get("wind", {}).get("speed", 0)

    current_rain = weather.get("rain", {}).get("1h", 0)

    prev_month_rain = current_30d

    rain_2month_sum = current_30d + previous_30d

    rain_variability = abs(rain_24h - (rain_7d / 7))

    rain_intensity = current_30d / 30

    rain_momentum = current_rain * wind

    monsoon_cumulative = (0.6 * current_30d) + (0.4 * previous_30d)

    monsoon_saturation = min(1, monsoon_cumulative / 500)

    rain_anomaly = rain_24h - 10

    extreme_rain = 1 if rainfall > 50 else 0

    features = [

        terrain["elevation"],
        terrain["slope"],
        terrain["river_distance"],
        terrain["relative_elevation"],
        terrain["terrain_ruggedness"],
        terrain["drainage_potential"],
        terrain["river_importance"],
        terrain["twi"],

        rainfall,
        rain_intensity,
        rain_momentum,
        prev_month_rain,
        rain_2month_sum,
        monsoon_cumulative,
        monsoon_saturation,
        rain_anomaly,
        extreme_rain
    ]

    return features, rainfall, wind, current_rain

# NOTIFICATION FUNCTION
SCOPES = ["https://www.googleapis.com/auth/firebase.messaging"]

def get_access_token():
    credentials = service_account.Credentials.from_service_account_file(
        "service-account.json",
        scopes=SCOPES
    )
    credentials.refresh(Request())
    return credentials.token


def send_notification(state, district):

    access_token = get_access_token()

    url = "https://fcm.googleapis.com/v1/projects/sachetna-9fd72/messages:send"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    payload = {
        "message": {
            "topic": "all",  
            "notification": {
                "title": "Flood Alert",
                "body": f"High flood risk in {district}, {state}"
            }
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    print(response.text)

# MAIN PREDICTION

@app.post("/predict/{state}/{district}")
def predict_flood(state: str, district: str, req: FloodRequest):

    try:
        coords = get_coordinates(state, district)
        lat = coords["lat"]
        lon = coords["lon"]

        # Current weather
        weather = get_weather(lat, lon)

        # Past rainfall (60-day based)
        rain_24h, rain_7d, current_30d, previous_30d, past_60days = get_openmeteo_rainfall(lat, lon)

        # Forecast data
        forecast_list = get_forecast_data(lat, lon)
        daily_forecast = process_forecast_daily(forecast_list)

        future_predictions = []

        # CURRENT PREDICTION
        features, rainfall, wind, current_rain = build_features(
            lat,
            lon,
            weather,
            rain_24h,
            rain_7d,
            current_30d,
            previous_30d
        )

        X = np.array(features).reshape(1, -1)
        prob = model.predict_proba(X)[0][1]

        if prob <= 0.75:
            risk = "Low"
        elif prob <= 0.90:
            risk = "Moderate"
        else:
            risk = "High"

        # FUTURE PREDICTIONS
        if risk == "High":
            send_notification(state, district)

        coords = get_coordinates(state, district)

        with user_handler.db.get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "DELETE FROM risk_markers WHERE state=? AND district=?",
                (state, district)
            )

            if risk.lower() != "low":
                cur.execute(
                    "INSERT INTO risk_markers (state, district, risk, lat, lon, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                    (state, district, risk, coords["lat"], coords["lon"], time.time())
                )

        # FIX: use last 7 days from 60-day history
        rolling_window = past_60days[-7:].copy()
        rolling_30d = past_60days[-30:].copy()
        rolling_prev30d = past_60days[-60:-30].copy()

        for day in daily_forecast:

            # use past-only data first
            dynamic_rain_7d = sum(rolling_window)
            future_rain_24h = day["rain"]

            sim_current_30d = sum(rolling_30d)
            sim_previous_30d = sum(rolling_prev30d)

            # Simulated weather for that day
            fake_weather = {
                "main": {
                    "temp": day["temp"],
                    "humidity": day["humidity"],
                },
                "wind": {"speed": day["wind"]},
                "rain": {"1h": day["rain_max"] / 3}
            }

            # pass correct params
            features, _, _, _ = build_features(
                lat,
                lon,
                fake_weather,
                future_rain_24h,
                dynamic_rain_7d,
                sim_current_30d,
                sim_previous_30d
            )

            X_future = np.array(features).reshape(1, -1)
            prob_future = model.predict_proba(X_future)[0][1]

            future_predictions.append({
                "date": day["date"],
                "risk": round(float(prob_future), 3)
            })

            # update AFTER prediction (correct time logic)
            rolling_window.append(day["rain"])
            rolling_window = rolling_window[-7:]

            rolling_30d.append(day["rain"])
            rolling_30d = rolling_30d[-30:]

            rolling_prev30d.append(rolling_30d[0])
            rolling_prev30d = rolling_prev30d[-30:]

        # RESPONSE
        return {
            "state": state,
            "district": district,

            "current_prediction": {
                "risk_level": risk,
                "score": round(float(prob), 3)
            },

            "future_predictions": future_predictions,

            "features": {
                "temp": weather["main"]["temp"],
                "humidity": weather["main"]["humidity"],
                "wind_speed": wind,
                "current_rain": current_rain,
                "rain_24h": rain_24h,
                "rain_7d": rain_7d,
                "current_30d": current_30d,
                "previous_30d": previous_30d
            }
        }

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# PREDICT BY COORDINATES

@app.post("/predict-by-coordinates")
def predict_by_coordinates(req: CoordinateRequest):

    weather = get_weather(req.latitude, req.longitude)

    rain_24h, rain_7d, current_30d, previous_30d, _ = get_openmeteo_rainfall(req.latitude, req.longitude)

    features, rainfall, wind = features(
        req.latitude,
        req.longitude,
        weather,
        rain_24h,
        rain_7d,
        current_30d, 
        previous_30d
    )

    X = np.array(features).reshape(1, -1)

    prob = model.predict_proba(X)[0][1]

    return {

        "risk_score": float(prob),

        "temperature": weather["main"]["temp"],

        "humidity": weather["main"]["humidity"],

        "wind": wind,

        "rainfall": rainfall
    }

# AUTHENTICATION

@app.post("/auth/signup")
def signup(req: SignupRequest):

    created = user_handler.register(req.username, req.password, req.full_name)

    if not created:
        raise HTTPException(status_code=400, detail="Username already exists")

    return {"status": "success", "message": "Account created"}


@app.post("/auth/login")
def login(req: LoginRequest):

    if not user_handler.verify_credentials(req.username, req.password):

        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = user_handler.create_session(req.username)

    return {
        "status": "success",
        "token": token
    }


@app.get("/auth/validate")
def validate_session(token: str):

    uid = user_handler.validate_session(token)

    if not uid:
        raise HTTPException(status_code=401, detail="Session expired")

    return {"status": "valid"}


@app.post("/auth/logout")
def logout(token: str):

    uid = user_handler.validate_session(token)

    if uid:
        user_handler.logout(uid)

    return {"status": "success"}

# ROOT ENDPOINT

@app.get("/")
def root():
    return {"message": "Early Flood Predictor API running"}

@app.get("/coordinates/{state}/{district}")
def get_coords_api(state: str, district: str):
    coords = get_coordinates(state, district)
    return coords

# MARKER FETCH
@app.get("/markers")
def get_markers():
    with user_handler.db.get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT state, district, risk, lat, lon FROM risk_markers")
        rows = cur.fetchall()

    return [
        {
            "state": r[0],
            "district": r[1],
            "risk": r[2],
            "lat": r[3],
            "lon": r[4]
        }
        for r in rows
    ]

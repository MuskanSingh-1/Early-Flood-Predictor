import os
import json
import pickle
import requests
import pandas as pd
import numpy as np
import time
import traceback

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from scipy.spatial import KDTree

from auth import User
from bot import router as chat_router


# ===============================
# CONFIG
# ===============================

OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")

MODEL_PATH = "flood_xgboost_model.pkl"
TERRAIN_PATH = "terrain_lookup.json"
COORDINATE_PATH = "indian_district_coordinates.json"


# ===============================
# LOAD MODEL
# ===============================

try:
    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    print("✅ XGBoost model loaded successfully")

except Exception as e:
    raise RuntimeError(f"❌ Failed to load model: {e}")


# ===============================
# LOAD TERRAIN DATASET
# ===============================

with open("terrain_lookup.json", "r") as f:
    TERRAIN_DATA = json.load(f)

print("✅ Terrain dataset loaded")

# Extract coordinates
terrain_coords = [(p["lat"], p["lon"]) for p in TERRAIN_DATA]

# Build KDTree
terrain_tree = KDTree(terrain_coords)

print("✅ KDTree spatial index built")


# ===============================
# FASTAPI INITIALIZATION
# ===============================

user_handler = User()

app = FastAPI(title="🌊 Early Flood Predictor API", version="4.0")

app.include_router(chat_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===============================
# REQUEST MODELS
# ===============================

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


class FloodReport(BaseModel):
    latitude: float
    longitude: float


# ===============================
# DISTRICT COORDINATES
# ===============================

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


# ===============================
# WEATHER FETCH
# ===============================

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


# ===============================
# TERRAIN LOOKUP
# ===============================

def find_nearest_terrain(lat, lon):

    distance, index = terrain_tree.query((lat, lon))

    return TERRAIN_DATA[index]


# ===============================
# FEATURE GENERATION
# ===============================

def build_features(lat, lon, weather):

    terrain = find_nearest_terrain(lat, lon)

    rainfall = weather.get("rain", {}).get("1h", 0)

    wind = weather.get("wind", {}).get("speed", 0)

    rain_intensity = rainfall

    rain_momentum = rainfall * wind

    prev_month_rain = rainfall * 20

    rain_2month_sum = prev_month_rain + rainfall

    monsoon_cumulative = rain_2month_sum

    monsoon_saturation = min(1, monsoon_cumulative / 500)

    rain_anomaly = rainfall - 10

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

    return features, rainfall, wind


# ===============================
# MAIN PREDICTION
# ===============================

@app.post("/predict/{state}/{district}")
def predict_flood(state: str, district: str, req: FloodRequest):

    try:

        coords = get_coordinates(state, district)

        weather = get_weather(coords["lat"], coords["lon"])

        features, rainfall, wind = build_features(
            coords["lat"],
            coords["lon"],
            weather
        )

        X = np.array(features).reshape(1, -1)

        prob = model.predict_proba(X)[0][1]

        if prob < 0.30:
            risk = "Low"
        elif prob < 0.65:
            risk = "Moderate"
        else:
            risk = "High"

        return {

            "state": state,
            "district": district,

            "risk_level": risk,

            "score": round(float(prob), 3),

            "features": {
                "temp": weather["main"]["temp"],
                "humidity": weather["main"]["humidity"],
                "wind_speed": wind,
                "rainfall": rainfall
            }
        }

    except Exception as e:

        traceback.print_exc()

        raise HTTPException(status_code=500, detail=str(e))


# ===============================
# PREDICT BY COORDINATES
# ===============================

@app.post("/predict-by-coordinates")
def predict_by_coordinates(req: CoordinateRequest):

    weather = get_weather(req.latitude, req.longitude)

    features, rainfall, wind = build_features(
        req.latitude,
        req.longitude,
        weather
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


# ===============================
# AUTHENTICATION
# ===============================

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


# ===============================
# FLOOD REPORTING
# ===============================

@app.post("/report-flood")
def report_flood(data: FloodReport):

    report = {
        "lat": data.latitude,
        "lon": data.longitude,
        "time": datetime.now().isoformat()
    }

    with open("flood_reports.json", "a") as f:
        f.write(json.dumps(report) + "\n")

    return {"message": "Flood report saved"}


# ===============================
# ROOT ENDPOINT
# ===============================

@app.get("/")
def root():
    return {"message": "🌊 Early Flood Predictor API running"}

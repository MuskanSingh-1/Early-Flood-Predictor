import os
import json
import pickle
import requests
import pandas as pd
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
from auth import User
import lightgbm as lgb
import traceback

# WEATHER FETCH FUNCTION
API_KEY = "3a3c8df5e95f29bd818c6649a2abf589"

def get_weather_data(district, state=None):
    try:
        if state:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={district},{state},IN&appid={API_KEY}&units=metric"
        else:
            url = f"https://api.openweathermap.org/data/2.5/weather?q={district}&appid={API_KEY}&units=metric"
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Weather fetch error: {e}")
        return None

# CONFIGURATION
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY") or API_KEY
if not OPENWEATHER_API_KEY:
    raise RuntimeError("❌ Please set your OpenWeatherMap API key using: set OPENWEATHER_API_KEY=your_api_key_here")

MODEL_PATH = "ensemble_1.pkl"

# MODEL LOADING
try:
    with open(MODEL_PATH, "rb") as f:
        model_data = pickle.load(f)

    if isinstance(model_data, lgb.Booster):
        model = model_data
        print("✅ Loaded single LightGBM Booster model successfully.")

    elif isinstance(model_data, lgb.LGBMRegressor):
        model = model_data.booster_
        print("✅ Loaded LGBMRegressor and converted to Booster.")

    elif isinstance(model_data, dict):
        ensemble_models = []
        for k, v in model_data.items():
            if isinstance(v, (lgb.Booster, lgb.LGBMRegressor)):
                if isinstance(v, lgb.LGBMRegressor):
                    v = v.booster_
                ensemble_models.append(v)
                print(f"✅ Added model '{k}' to ensemble.")
        if not ensemble_models:
            raise ValueError("No valid models found inside ensemble dictionary.")
        model = ensemble_models
        print(f"✅ Loaded ensemble with {len(ensemble_models)} models.")
    else:
        raise ValueError(f"Unsupported model type: {type(model_data)}")

except Exception as e:
    raise RuntimeError(f"❌ Error loading model: {e}")

# FASTAPI APP INITIALIZATION
user_handler = User()
app = FastAPI(title="🌊 Early Flood Predictor API", version="3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# REQUEST BODY MODEL
class FloodRequest(BaseModel):
    timestamp: float = 0.0

# CASE-INSENSITIVE COORDINATE LOOKUP
def get_coordinates(state: str, district: str):
    try:
        with open("indian_district_coordinates.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="Coordinate file 'indian_district_coordinates.json' not found")

    state_key = next((s for s in data.keys() if s.lower() == state.lower()), None)
    if not state_key:
        raise HTTPException(status_code=404, detail=f"State '{state}' not found")

    district_key = next((d for d in data[state_key].keys() if d.lower() == district.lower()), None)
    if not district_key:
        raise HTTPException(status_code=404, detail=f"District '{district}' not found in '{state_key}'")

    return data[state_key][district_key]

# WEATHER FETCH FUNCTION (Coordinate-based)
def get_weather(lat: float, lon: float):
    params = {"lat": lat, "lon": lon, "appid": OPENWEATHER_API_KEY, "units": "metric"}
    try:
        resp = requests.get("https://api.openweathermap.org/data/2.5/weather", params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if "main" not in data:
            raise HTTPException(status_code=500, detail=f"Weather API error: {data}")
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Weather fetch error: {e}")

# SAFE PREDICT FUNCTION
def safe_predict(model, X: pd.DataFrame):
    """Predict safely for LightGBM Booster or ensemble of Boosters with feature shape check."""
    try:
        # Ensemble handling
        if isinstance(model, list):
            preds = []
            for i, m in enumerate(model):
                expected_features = m.num_feature()
                actual_features = X.shape[1]

                # If extra columns, trim
                if actual_features > expected_features:
                    X_adj = X.iloc[:, :expected_features]
                    print(f"⚙️ Trimmed input for model {i+1}: expected {expected_features}, got {actual_features}")
                else:
                    X_adj = X

                pred = m.predict(X_adj.values, num_iteration=m.best_iteration, predict_disable_shape_check=True)
                preds.append(pred)
            preds = sum(preds) / len(preds)
            return preds

        else:
            # Single model
            expected_features = model.num_feature()
            actual_features = X.shape[1]

            if actual_features > expected_features:
                X = X.iloc[:, :expected_features]
                print(f"⚙️ Trimmed input: expected {expected_features}, got {actual_features}")
            elif actual_features < expected_features:
                raise HTTPException(
                    status_code=400,
                    detail=f"Model expects {expected_features} features but got {actual_features}"
                )

            preds = model.predict(X.values, num_iteration=model.best_iteration, predict_disable_shape_check=True)
            return preds

    except Exception as e:
        raise RuntimeError(f"Model prediction failed: {e}")
    
class SignupRequest(BaseModel):
    username: str
    password: str
    full_name: str = ""

class LoginRequest(BaseModel):
    username: str
    password: str

# PREDICTION ENDPOINT
TRAINING_FEATURE_ORDER = [
    "Flood_Frequency",
    "Mean_Duration",
    "Human_fatality",
    "Human_injured",
    "Population",
    "Corrected_Percent_Flooded_Area",
    "Population_Exposure_Ratio",
    "Area_Exposure",
    "Mean_Flood_Duration",
    "Percent_Flooded_Area",
    "Parmanent_Water",
    "Year"
]

# FLOOD IMPACT CONSTANTS
ALPHA = 0.0475
BETA = 0.1057
GAMMA = 0.8468


@app.post("/predict/{state}/{district}")
def predict_flood(state: str, district: str, req: FloodRequest):
    try:
        coords = get_coordinates(state, district)
        weather = get_weather(coords["lat"], coords["lon"])

        temp = weather["main"].get("temp", 0.0)
        humidity = weather["main"].get("humidity", 0.0)
        pressure = weather["main"].get("pressure", 0.0)
        wind_speed = weather.get("wind", {}).get("speed", 0.0)
        rain = weather.get("rain", {})
        rainfall = rain.get("1h") if "1h" in rain else rain.get("3h", 0.0)
        year = int(pd.Timestamp.now().year)

        Flood_Frequency = rainfall / 50          
        Mean_Duration = rainfall / 10            
        Human_fatality = 0                       
        Human_injured = 0
        Population = 1460000

        Percent_Flooded_Area = min(100.0, max(0.0, (rainfall * 10) + (humidity * 0.05) + (wind_speed * 2)))
        ExposedPopulation = Population * (Percent_Flooded_Area / 100)
        Population_Exposure_Ratio = ExposedPopulation / Population

        Corrected_Percent_Flooded_Area = Percent_Flooded_Area
        Area_Exposure = Percent_Flooded_Area / 100.0
        Mean_Flood_Duration = rainfall / 8.0
        Parmanent_Water = humidity / 120.0

        Population_Exposure_Ratio = humidity / 100
        Area_Exposure = rainfall * 0.2
        Mean_Flood_Duration = rainfall / 8
        Percent_Flooded_Area = rainfall * 0.5
        Parmanent_Water = humidity / 120

        Flood_Risk_Index = rainfall + humidity + temp / 10

        # small baseline to avoid absolute zero
        EPSILON = 0.05

        base_risk = max(rainfall, EPSILON)

        Flood_Impact_Index = base_risk * (
            (1 + ALPHA * Mean_Duration) *
            (1 + BETA * Flood_Frequency) *
            (1 + GAMMA * Population_Exposure_Ratio)
        )

        current_risk_score = min(1.0, Flood_Impact_Index / 10)
        pred = current_risk_score
        features = pd.DataFrame([training_values], columns=TRAINING_FEATURE_ORDER)

        pred_ml = float(safe_predict(model, features)[0])

        # STEP 5: Final risk interpretation
        if pred_ml < 0.33:
            risk_level = "Low"
        elif pred_ml < 0.66:
            risk_level = "Moderate"
        else:
            risk_level = "High"

        features_for_frontend = {
            "temp": temp,
            "humidity": humidity,
            "wind_speed": wind_speed,
            "rainfall": rainfall
        }

        return {
            "status": "success",
            "state": state,
            "district": district,

            # The ONLY place frontend reads weather data from
            "features": features_for_frontend,
            "features_used": features_for_frontend,

            # Training model inputs
            "model_features_used": dict(zip(TRAINING_FEATURE_ORDER, training_values)),

            # Flood impact + prediction
            "Flood_Impact_Index": round(Flood_Impact_Index, 4),
            "predicted_flood_risk": round(pred, 4),
            "risk_level": risk_level
        }


    except Exception as e:
        print("\n🔥 Inference error:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Inference error: {e}")

@app.post("/auth/signup")
def signup(req: SignupRequest):
    try:
        created = user_handler.register(req.username, req.password, req.full_name)
        if not created:
            raise HTTPException(status_code=400, detail="Username already exists")
        return {"status": "success", "message": "✅ Account created successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auth/login")
def login(req: LoginRequest):
    try:
        if not user_handler.verify_credentials(req.username, req.password):
            raise HTTPException(status_code=401, detail="Invalid username or password")

        token = user_handler.create_session(req.username)

        return {
            "status": "success",
            "message": "✅ Login successful",
            "token": token
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/validate")
def validate_session(token: str):
    uid = user_handler.validate_session(token)
    if not uid:
        raise HTTPException(status_code=401, detail="Session expired or invalid")
    return {"status": "valid"}

@app.post("/auth/logout")
def logout(token: str):
    uid = user_handler.validate_session(token)
    if uid:
        user_handler.logout(uid)
    return {"status": "success", "message": "Logged out successfully"}

# ROOT ENDPOINT
@app.get("/")
def root():
    return {"message": "🌊 Early Flood Predictor API is running successfully!"}

# 🚰 Drought Prediction & Tanker Allocation API

FastAPI backend for the Hack-a-Cause hackathon.

## ⚡ Quick Start

```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Swagger docs → http://localhost:8000/docs

---

## 📡 Endpoints

| Method | Endpoint     | Description                          |
|--------|--------------|--------------------------------------|
| GET    | `/`          | Health check                         |
| POST   | `/analyze`   | Analyze regions, get WSI + tankers   |
| GET    | `/dashboard` | KPIs + stress distribution           |
| GET    | `/routes`    | Ordered tanker dispatch routes       |

---

## 🧮 Model

```
WSI = 0.4 × rainfall_deviation + 0.3 × groundwater_decline + 0.3 × population_factor

rainfall_deviation  = (normal_rainfall − actual_rainfall) / normal_rainfall
groundwater_decline = (100 − groundwater_level) / 100
population_factor   = population / max_population

Stress:  < 0.3 → safe | 0.3–0.6 → moderate | > 0.6 → critical

daily_need      = population × 135
available_water = population × groundwater_level × 0.5
deficit         = daily_need − available_water
tankers         = ceil(deficit / 10000)

priority_score  = 0.7 × WSI + 0.3 × population_factor
```

---

## 🔁 Example Request

```bash
curl -X POST http://localhost:8000/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "regions": [
      {
        "region_id": "R001",
        "region_name": "Nagpur East",
        "population": 45000,
        "normal_rainfall": 800.0,
        "actual_rainfall": 320.0,
        "groundwater_level": 35.0,
        "max_population": 100000
      },
      {
        "region_id": "R002",
        "region_name": "Wardha Rural",
        "population": 12000,
        "normal_rainfall": 750.0,
        "actual_rainfall": 600.0,
        "groundwater_level": 65.0,
        "max_population": 100000
      }
    ]
  }'
```

## 📊 Example Response (trimmed)

```json
{
  "success": true,
  "summary": {
    "total_regions": 2,
    "critical_count": 1,
    "moderate_count": 1,
    "safe_count": 0,
    "total_tankers_needed": 312
  },
  "regions": [...]
}
```

"""
Drought Prediction & Tanker Allocation System - FastAPI Backend
Hackathon-ready backend using Water Stress Index (WSI) model
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional
import math

# ─────────────────────────────────────────────
#  App Setup
# ─────────────────────────────────────────────
app = FastAPI(
    title="Drought Prediction & Tanker Allocation API",
    description="Predicts drought stress and allocates water tankers using WSI model",
    version="1.0.0"
)

# CORS — allow React frontend on any localhost port
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # tighten in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────
#  Pydantic Models
# ─────────────────────────────────────────────
class RegionInput(BaseModel):
    """Input data for a single region/village/ward."""
    region_id: str = Field(..., example="R001")
    region_name: str = Field(..., example="Nagpur East")
    population: int = Field(..., example=45000, gt=0)
    normal_rainfall: float = Field(..., example=800.0, description="mm, historical average")
    actual_rainfall: float = Field(..., example=320.0, description="mm, this season")
    groundwater_level: float = Field(..., example=35.0, description="% of max capacity (0–100)")
    max_population: int = Field(..., example=100000, description="Max population in the dataset")


class AnalyzeRequest(BaseModel):
    """Request body for /analyze — accepts multiple regions."""
    regions: List[RegionInput]

    class Config:
        json_schema_extra = {
            "example": {
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
            }
        }


# ─────────────────────────────────────────────
#  Core Calculation Functions
# ─────────────────────────────────────────────
def compute_wsi(
    normal_rainfall: float,
    actual_rainfall: float,
    groundwater_level: float,
    population: int,
    max_population: int
) -> dict:
    """
    Compute Water Stress Index (WSI) and its components.

    WSI = 0.4 × rainfall_deviation + 0.3 × groundwater_decline + 0.3 × population_factor
    """
    # Component 1: Rainfall deviation (higher = worse)
    rainfall_deviation = (normal_rainfall - actual_rainfall) / normal_rainfall
    rainfall_deviation = max(0.0, min(1.0, rainfall_deviation))  # clamp to [0, 1]

    # Component 2: Groundwater decline (higher level = lower stress)
    groundwater_decline = (100 - groundwater_level) / 100
    groundwater_decline = max(0.0, min(1.0, groundwater_decline))

    # Component 3: Population factor (relative pressure on resources)
    population_factor = population / max_population
    population_factor = max(0.0, min(1.0, population_factor))

    # Final WSI score
    wsi = (
        0.4 * rainfall_deviation +
        0.3 * groundwater_decline +
        0.3 * population_factor
    )

    return {
        "wsi": round(wsi, 4),
        "rainfall_deviation": round(rainfall_deviation, 4),
        "groundwater_decline": round(groundwater_decline, 4),
        "population_factor": round(population_factor, 4),
    }


def get_stress_level(wsi: float) -> str:
    """Classify WSI into stress categories."""
    if wsi < 0.3:
        return "safe"
    elif wsi <= 0.6:
        return "moderate"
    else:
        return "critical"


def compute_tankers(population: int, groundwater_level: float) -> dict:
    """
    Predict daily tanker requirement.

    daily_need     = population × 135 litres
    available_water = population × groundwater_level × 0.5
    deficit        = daily_need − available_water
    tankers_needed = deficit / 10,000 litres per tanker
    """
    daily_need = population * 135
    available_water = population * groundwater_level * 0.5
    deficit = max(0.0, daily_need - available_water)
    tankers = math.ceil(deficit / 10000)

    return {
        "daily_need_litres": round(daily_need, 2),
        "available_water_litres": round(available_water, 2),
        "deficit_litres": round(deficit, 2),
        "tankers_needed": tankers,
    }


def compute_priority_score(wsi: float, population_factor: float) -> float:
    """Priority score for tanker dispatch ordering."""
    return round(0.7 * wsi + 0.3 * population_factor, 4)


def analyze_region(region: RegionInput) -> dict:
    """Run full analysis for one region and return enriched result."""
    wsi_data = compute_wsi(
        region.normal_rainfall,
        region.actual_rainfall,
        region.groundwater_level,
        region.population,
        region.max_population,
    )
    stress_level = get_stress_level(wsi_data["wsi"])
    tanker_data = compute_tankers(region.population, region.groundwater_level)
    priority = compute_priority_score(wsi_data["wsi"], wsi_data["population_factor"])

    return {
        "region_id": region.region_id,
        "region_name": region.region_name,
        "population": region.population,
        "wsi": wsi_data["wsi"],
        "stress_level": stress_level,
        "components": {
            "rainfall_deviation": wsi_data["rainfall_deviation"],
            "groundwater_decline": wsi_data["groundwater_decline"],
            "population_factor": wsi_data["population_factor"],
        },
        "tanker_allocation": tanker_data,
        "priority_score": priority,
    }


# ─────────────────────────────────────────────
#  In-memory store (replaces DB for hackathon)
# ─────────────────────────────────────────────
latest_analysis: List[dict] = []


# ─────────────────────────────────────────────
#  Endpoints
# ─────────────────────────────────────────────
@app.get("/", tags=["Health"])
def root():
    """Health check."""
    return {"status": "ok", "message": "Drought Prediction API is running 🚰"}


@app.post("/analyze", tags=["Analysis"])
def analyze(request: AnalyzeRequest):
    """
    POST /analyze

    Accept a list of regions with rainfall, groundwater, and population data.
    Returns WSI score, stress level, tanker requirement, and priority for each region.
    Results are stored in memory for /dashboard and /routes.
    """
    global latest_analysis

    if not request.regions:
        raise HTTPException(status_code=400, detail="No regions provided.")

    results = [analyze_region(r) for r in request.regions]

    # Sort by priority score descending (most critical first)
    results.sort(key=lambda x: x["priority_score"], reverse=True)

    # Persist for dashboard/routes
    latest_analysis = results

    # Summary stats
    total_tankers = sum(r["tanker_allocation"]["tankers_needed"] for r in results)
    critical = [r for r in results if r["stress_level"] == "critical"]
    moderate = [r for r in results if r["stress_level"] == "moderate"]
    safe     = [r for r in results if r["stress_level"] == "safe"]

    return {
        "success": True,
        "summary": {
            "total_regions": len(results),
            "critical_count": len(critical),
            "moderate_count": len(moderate),
            "safe_count": len(safe),
            "total_tankers_needed": total_tankers,
        },
        "regions": results,
    }


@app.get("/dashboard", tags=["Dashboard"])
def dashboard():
    """
    GET /dashboard

    Returns aggregated stats from the last /analyze call.
    Useful for rendering charts and KPI cards in the React frontend.
    """
    if not latest_analysis:
        return {
            "success": True,
            "message": "No analysis data yet. Call POST /analyze first.",
            "data": {}
        }

    total_tankers = sum(r["tanker_allocation"]["tankers_needed"] for r in latest_analysis)
    avg_wsi = round(sum(r["wsi"] for r in latest_analysis) / len(latest_analysis), 4)
    total_deficit = sum(r["tanker_allocation"]["deficit_litres"] for r in latest_analysis)

    stress_distribution = {
        "critical": len([r for r in latest_analysis if r["stress_level"] == "critical"]),
        "moderate": len([r for r in latest_analysis if r["stress_level"] == "moderate"]),
        "safe":     len([r for r in latest_analysis if r["stress_level"] == "safe"]),
    }

    # Top 5 most critical regions
    top_critical = latest_analysis[:5]

    return {
        "success": True,
        "kpis": {
            "total_regions_analysed": len(latest_analysis),
            "average_wsi": avg_wsi,
            "total_tankers_needed": total_tankers,
            "total_water_deficit_litres": round(total_deficit, 2),
        },
        "stress_distribution": stress_distribution,
        "top_critical_regions": top_critical,
        "all_regions": latest_analysis,
    }


@app.get("/routes", tags=["Routing"])
def routes():
    """
    GET /routes

    Returns ordered tanker dispatch routes.
    Regions sorted by priority score (highest first = most urgent).
    Only includes regions that actually need tankers.
    """
    if not latest_analysis:
        return {
            "success": True,
            "message": "No analysis data yet. Call POST /analyze first.",
            "routes": []
        }

    # Filter regions needing tankers, already sorted by priority
    dispatch_list = [
        {
            "dispatch_order": idx + 1,
            "region_id": r["region_id"],
            "region_name": r["region_name"],
            "stress_level": r["stress_level"],
            "priority_score": r["priority_score"],
            "tankers_to_dispatch": r["tanker_allocation"]["tankers_needed"],
            "deficit_litres": r["tanker_allocation"]["deficit_litres"],
            "population": r["population"],
        }
        for idx, r in enumerate(latest_analysis)
        if r["tanker_allocation"]["tankers_needed"] > 0
    ]

    return {
        "success": True,
        "total_tankers_dispatching": sum(d["tankers_to_dispatch"] for d in dispatch_list),
        "routes": dispatch_list,
    }

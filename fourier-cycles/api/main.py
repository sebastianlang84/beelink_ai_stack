import os
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Fourier Cycles API")

# Enable CORS for the UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OUTPUT_DIR = os.getenv("FOURIER_OUTPUT_DIR", "/app/output")

@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "fourier-cycles-api"}

@app.get("/api/runs")
def list_runs():
    return {"runs": ["latest"]}

@app.get("/api/runs/latest/series")
def list_latest_series():
    latest_dir = os.path.join(OUTPUT_DIR, "latest")
    if not os.path.isdir(latest_dir):
        return {"series": []}
    
    series_list = []
    for item in sorted(os.listdir(latest_dir)):
        item_path = os.path.join(latest_dir, item)
        if os.path.isdir(item_path):
            summary_path = os.path.join(item_path, "summary.json")
            if os.path.exists(summary_path):
                try:
                    with open(summary_path, "r") as f:
                        data = json.load(f)
                        series_list.append({
                            "id": item,
                            "source": data.get("source"),
                            "name": data.get("series")
                        })
                except Exception as e:
                    pass
    return {"series": series_list}

@app.get("/api/runs/latest/series/{series_id}")
def get_latest_series_detail(series_id: str):
    summary_path = os.path.join(OUTPUT_DIR, "latest", series_id, "summary.json")
    if not os.path.exists(summary_path):
        raise HTTPException(status_code=404, detail="Series not found")
    try:
        with open(summary_path, "r") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error reading series data")

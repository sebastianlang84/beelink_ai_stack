from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Fourier Cycles API")

# Enable CORS for the UI (we'll limit this later if needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/healthz")
def healthz():
    return {"status": "ok", "service": "fourier-cycles-api"}

@app.get("/api/runs")
def list_runs():
    # Placeholder for Phase B where we index the output directory
    return {"runs": []}

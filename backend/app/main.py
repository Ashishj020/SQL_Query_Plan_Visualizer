from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .explain import analyze_sql, health
from .models import AnalyzeRequest, AnalyzeResponse, HealthResponse, SampleQuery
from .samples import SAMPLES
from .security import UnsafeSqlError

app = FastAPI(title="Planlight", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    payload = health()
    return HealthResponse(
        ok=bool(payload.get("ok")),
        database=str(payload.get("database") or "unknown"),
        postgres_version=payload.get("postgres_version"),
        detail=payload.get("detail"),
    )


@app.get("/api/samples", response_model=list[SampleQuery])
def get_samples() -> list[SampleQuery]:
    return SAMPLES


@app.post("/api/analyze", response_model=AnalyzeResponse)
def post_analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    try:
        return analyze_sql(body.sql, run_analyze=body.analyze)
    except UnsafeSqlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # surface planner / timeout errors
        raise HTTPException(status_code=500, detail=str(exc)) from exc

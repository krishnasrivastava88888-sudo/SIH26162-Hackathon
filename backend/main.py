from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.hotspots import router as hotspots_router
from backend.routes.facilities import router as facilities_router
from backend.routes.events import router as events_router
from backend.routes.alerts import router as alerts_router
from backend.routes.statistics import router as statistics_router

app = FastAPI(title="ThermoGuard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "message": "ThermoGuard API is running"
    }


app.include_router(hotspots_router)
app.include_router(facilities_router)
app.include_router(events_router)
app.include_router(alerts_router)
app.include_router(statistics_router)
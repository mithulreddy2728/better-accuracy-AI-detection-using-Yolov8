from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.database import engine, Base
from routers import auth, cameras, geo_markers, vehicles, upload, live_feed
from app.process_manager import stop_all, cleanup_orphans
import os

# Cleanup any orphan detection processes from previous runs
cleanup_orphans()

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Nozzle Detection & Vehicle Monitoring System", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files directory for media files
media_dir = os.path.join(os.path.dirname(__file__), "media")
if not os.path.exists(media_dir):
    os.makedirs(media_dir)
app.mount("/media", StaticFiles(directory=media_dir), name="media")

# Include routers
app.include_router(auth.router, prefix="", tags=["Authentication"])  # POST /login
app.include_router(cameras.router, prefix="/camera", tags=["Cameras"])
app.include_router(geo_markers.router, prefix="/geo-marker", tags=["Geo Markers"])
app.include_router(vehicles.router, prefix="/vehicle", tags=["Vehicles/Detections"])
app.include_router(upload.router, prefix="/upload", tags=["Upload"])
app.include_router(live_feed.router, prefix="/live-feed", tags=["Live Feed"])

@app.get("/")
def read_root():
    return {"message": "AI Nozzle Detection & Vehicle Monitoring System API"}

@app.on_event("shutdown")
def shutdown_event():
    """Stop all active detection processes on server shutdown"""
    print("Shutting down: Stopping all detection processes...")
    stop_all()

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from models.models import GeoMarker
from schemas.schemas import GeoMarkerCreate, GeoMarker as GeoMarkerSchema
from auth.auth import get_current_user

router = APIRouter()

@router.post("/add", response_model=GeoMarkerSchema)
def add_geo_marker(marker: GeoMarkerCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    db_marker = GeoMarker(camera_id=marker.camera_id, x1=marker.x1, y1=marker.y1, x2=marker.x2, y2=marker.y2)
    db.add(db_marker)
    db.commit()
    db.refresh(db_marker)
    return db_marker

@router.get("/by-camera/{camera_id}", response_model=list[GeoMarkerSchema])
def get_geo_markers_by_camera(camera_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    markers = db.query(GeoMarker).filter(GeoMarker.camera_id == camera_id).all()
    return markers

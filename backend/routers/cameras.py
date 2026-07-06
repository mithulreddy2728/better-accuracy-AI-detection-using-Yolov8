from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from models.models import Camera, GeoMarker, Detection
from schemas.schemas import CameraCreate, CameraUpdate, Camera as CameraSchema
from auth.auth import get_current_user

from app.process_manager import stop_process

router = APIRouter()

@router.post("/add", response_model=CameraSchema)
def add_camera(camera: CameraCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    db_camera = Camera(type=camera.type, source=camera.source, status=True)
    db.add(db_camera)
    db.commit()
    db.refresh(db_camera)
    return db_camera

@router.get("/list", response_model=list[CameraSchema])
def list_cameras(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    cameras = db.query(Camera).all()
    return cameras

@router.put("/status/{camera_id}", response_model=CameraSchema)
def update_camera_status(camera_id: int, camera_update: CameraUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # If deactivating, stop the process
    if not camera_update.status:
        stop_process(camera_id)
        
    camera.status = camera_update.status
    db.commit()
    db.refresh(camera)
    return camera

@router.put("/status", response_model=CameraSchema)
def update_camera_status_body(camera_id: int, camera_update: CameraUpdate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Alternative endpoint that accepts camera_id in body"""
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    # If deactivating, stop the process
    if not camera_update.status:
        stop_process(camera_id)
        
    camera.status = camera_update.status
    db.commit()
    db.refresh(camera)
    return camera

@router.delete("/delete/{camera_id}")
def delete_camera(camera_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Delete a camera and all associated data:
    - Geo markers
    - Detections
    """
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")

    # STOP detection process if running
    stop_process(camera_id)

    # Delete detections for this camera
    db.query(Detection).filter(Detection.camera_id == camera_id).delete()
    # Delete geo markers for this camera
    db.query(GeoMarker).filter(GeoMarker.camera_id == camera_id).delete()

    # Finally delete the camera
    db.delete(camera)
    db.commit()
    return {"message": "Camera and related data deleted successfully"}

@router.put("/processing-status/{camera_id}")
def update_processing_status(
    camera_id: int, 
    processing_status: str,
    completion_message: str = None,
    db: Session = Depends(get_db), 
    current_user: dict = Depends(get_current_user)
):
    """
    Update camera processing status
    Status values: idle, processing, completed, error
    """
    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    camera.processing_status = processing_status
    if completion_message:
        camera.completion_message = completion_message
    
    db.commit()
    db.refresh(camera)
    return camera

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.database import get_db
from models.models import Detection
from schemas.schemas import DetectionCreate, Detection as DetectionSchema
from auth.auth import get_current_user
from datetime import datetime, timedelta
from app.process_manager import stop_all

router = APIRouter()

# Valid detection types
VALID_DETECTION_TYPES = ["Fuel Nozzle", "Car", "Bike", "Human", "Truck"]

@router.post("/store", response_model=DetectionSchema)
def store_detection(detection: DetectionCreate, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # Validate detection type
    if detection.detection_type not in VALID_DETECTION_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid detection_type. Must be one of: {', '.join(VALID_DETECTION_TYPES)}")
    
    # Check if camera exists
    from models.models import Camera
    camera = db.query(Camera).filter(Camera.id == detection.camera_id).first()
    if not camera:
        # Camera not found - this is critical for stopping zombie processes
        raise HTTPException(status_code=404, detail=f"Camera {detection.camera_id} not found")
    
    # Parse timestamp or use current time
    if detection.timestamp:
        try:
            timestamp = datetime.fromisoformat(detection.timestamp.replace('Z', '+00:00'))
        except:
            timestamp = datetime.utcnow()
    else:
        timestamp = datetime.utcnow()
    
    # If track_id is provided, try to find an existing record with that track_id and camera_id
    existing = None
    if detection.track_id is not None:
        existing = db.query(Detection).filter(
            and_(
                Detection.camera_id == detection.camera_id,
                Detection.track_id == detection.track_id,
                Detection.status == "active"
            )
        ).first()
    
    if not existing and detection.track_id is None:
        # Fallback to time-based window for older clients or if track_id is missing
        time_threshold = timestamp - timedelta(seconds=5)
        existing = db.query(Detection).filter(
            and_(
                Detection.camera_id == detection.camera_id,
                Detection.detection_type == detection.detection_type,
                Detection.status == "active",
                Detection.timestamp >= time_threshold
            )
        ).first()
    
    if existing:
        # Update existing detection
        existing.confidence_score = detection.confidence_score
        existing.timestamp = timestamp
        existing.object_image = detection.object_image
        existing.geo_marker_id = detection.geo_marker_id  # Update geo_marker_id
        
        # Only update plate info if we have better data
        if detection.numberplate_text and detection.numberplate_text.strip():
            existing.numberplate_text = detection.numberplate_text
            if detection.numberplate_image:
                existing.numberplate_image = detection.numberplate_image
        
        if detection.person_image:
            existing.person_image = detection.person_image
            
        db.commit()
        db.refresh(existing)
        
        # Print update confirmation
        print(f"✓ Detection updated: ID={existing.id}, Type={existing.detection_type}, Camera={existing.camera_id}, Confidence={existing.confidence_score:.2f}")
        if existing.track_id:
            print(f"  [Track {existing.track_id}] {existing.detection_type} updated. Plate: {existing.numberplate_text or '-no plate-'}")
        
        # Return dict with manually converted timestamp
        return {
            "id": existing.id,
            "camera_id": existing.camera_id,
            "geo_marker_id": existing.geo_marker_id,
            "detection_type": existing.detection_type,
            "confidence_score": existing.confidence_score,
            "object_image": existing.object_image,
            "numberplate_image": existing.numberplate_image,
            "numberplate_text": existing.numberplate_text,
            "person_image": existing.person_image,
            "track_id": existing.track_id,
            "timestamp": existing.timestamp.isoformat(),
            "status": existing.status
        }
    else:
        # Create new detection
        print(f"DEBUG: Received confidence_score from AI engine: {detection.confidence_score} (type: {type(detection.confidence_score)})")
        db_detection = Detection(
            camera_id=detection.camera_id,
            geo_marker_id=detection.geo_marker_id,
            detection_type=detection.detection_type,
            confidence_score=detection.confidence_score,
            object_image=detection.object_image,
            numberplate_image=detection.numberplate_image,
            numberplate_text=detection.numberplate_text,
            person_image=detection.person_image,
            track_id=detection.track_id,
            timestamp=timestamp,
            status="active"
        )
        db.add(db_detection)
        db.commit()
        db.refresh(db_detection)
        
        # Print confirmation
        print(f"✓ Detection stored: ID={db_detection.id}, Type={db_detection.detection_type}, Camera={db_detection.camera_id}, Confidence={db_detection.confidence_score:.2f}")
        
        # Count active detections for this camera
        active_count = db.query(Detection).filter(
            and_(
                Detection.camera_id == detection.camera_id,
                Detection.status == "active"
            )
        ).count()
        print(f"  Total active detections for camera {detection.camera_id}: {active_count}")
        
        # Return dict with manually converted timestamp
        return {
            "id": db_detection.id,
            "camera_id": db_detection.camera_id,
            "geo_marker_id": db_detection.geo_marker_id,
            "detection_type": db_detection.detection_type,
            "confidence_score": db_detection.confidence_score,
            "object_image": db_detection.object_image,
            "numberplate_image": db_detection.numberplate_image,
            "numberplate_text": db_detection.numberplate_text,
            "person_image": db_detection.person_image,
            "track_id": db_detection.track_id,
            "timestamp": db_detection.timestamp.isoformat(),
            "status": db_detection.status
        }

@router.get("/active")
def get_active_detections(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # Auto-expire old detections (older than 1 hour)
    expiry_time = datetime.utcnow() - timedelta(hours=1)
    db.query(Detection).filter(
        and_(
            Detection.timestamp < expiry_time,
            Detection.status == "active"
        )
    ).update({"status": "inactive"})
    db.commit()
    
    detections = db.query(Detection).filter(Detection.status == "active").order_by(Detection.timestamp.desc()).all()
    
    return [{
        "id": d.id,
        "camera_id": d.camera_id,
        "geo_marker_id": d.geo_marker_id,
        "detection_type": d.detection_type,
        "confidence_score": d.confidence_score,
        "object_image": d.object_image,
        "numberplate_image": d.numberplate_image,
        "numberplate_text": d.numberplate_text,
        "person_image": d.person_image,
        "track_id": d.track_id,
        "timestamp": d.timestamp.isoformat(),
        "status": d.status
    } for d in detections]

@router.get("/by-camera/{camera_id}")
def get_detections_by_camera(camera_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    detections = db.query(Detection).filter(
        and_(
            Detection.camera_id == camera_id,
            Detection.status == "active"
        )
    ).order_by(Detection.timestamp.desc()).all()
    
    return [{
        "id": d.id,
        "camera_id": d.camera_id,
        "geo_marker_id": d.geo_marker_id,
        "detection_type": d.detection_type,
        "confidence_score": d.confidence_score,
        "object_image": d.object_image,
        "numberplate_image": d.numberplate_image,
        "numberplate_text": d.numberplate_text,
        "person_image": d.person_image,
        "track_id": d.track_id,
        "timestamp": d.timestamp.isoformat(),
        "status": d.status
    } for d in detections]

@router.get("/by-type/{detection_type}")
def get_detections_by_type(detection_type: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if detection_type not in VALID_DETECTION_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid detection_type. Must be one of: {', '.join(VALID_DETECTION_TYPES)}")
    
    detections = db.query(Detection).filter(
        and_(
            Detection.detection_type == detection_type,
            Detection.status == "active"
        )
    ).order_by(Detection.timestamp.desc()).all()
    
    return [{
        "id": d.id,
        "camera_id": d.camera_id,
        "geo_marker_id": d.geo_marker_id,
        "detection_type": d.detection_type,
        "confidence_score": d.confidence_score,
        "object_image": d.object_image,
        "numberplate_image": d.numberplate_image,
        "numberplate_text": d.numberplate_text,
        "person_image": d.person_image,
        "track_id": d.track_id,
        "timestamp": d.timestamp.isoformat(),
        "status": d.status
    } for d in detections]

@router.get("/search")
def search_detections(
    camera_id: int = None,
    detection_type: str = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    query = db.query(Detection).filter(Detection.status == "active")
    
    if camera_id:
        query = query.filter(Detection.camera_id == camera_id)
    if detection_type:
        if detection_type not in VALID_DETECTION_TYPES:
            raise HTTPException(status_code=400, detail=f"Invalid detection_type. Must be one of: {', '.join(VALID_DETECTION_TYPES)}")
        query = query.filter(Detection.detection_type == detection_type)
    
    detections = query.order_by(Detection.timestamp.desc()).all()
    
    return [{
        "id": d.id,
        "camera_id": d.camera_id,
        "geo_marker_id": d.geo_marker_id,
        "detection_type": d.detection_type,
        "confidence_score": d.confidence_score,
        "object_image": d.object_image,
        "numberplate_image": d.numberplate_image,
        "numberplate_text": d.numberplate_text,
        "person_image": d.person_image,
        "track_id": d.track_id,
        "timestamp": d.timestamp.isoformat(),
        "status": d.status
    } for d in detections]

@router.delete("/delete-all")
def delete_all_detections(db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        # Stop all detection processes first
        stop_all()
        
        deleted_count = db.query(Detection).delete()
        db.commit()
        
        # Reset detection_service.log in both root and backend (legacy support)
        from pathlib import Path
        project_root = Path(__file__).parent.parent.parent
        log_paths = [
            project_root / "backend" / "detection_service.log",
            project_root / "detection_service.log"
        ]
        
        for log_path in log_paths:
            try:
                if log_path.exists():
                    with open(log_path, "w") as f:
                        f.write(f"--- Log reset at {datetime.now().isoformat()} ---\n")
            except Exception as e:
                print(f"Warning: Could not reset log file {log_path}: {e}")
            
        return {"message": f"Deleted {deleted_count} detections and reset logs", "count": deleted_count}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting detections: {str(e)}")

@router.get("/by-camera-geo-fence/{camera_id}")
def get_detections_by_camera_with_geo_fence(camera_id: int, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """Get all active detections for a camera that are within geo-fences"""
    detections = db.query(Detection).filter(
        and_(
            Detection.camera_id == camera_id,
            Detection.geo_marker_id.isnot(None),
            Detection.status == "active"
        )
    ).order_by(Detection.timestamp.desc()).all()
    
    return [{
        "id": d.id,
        "camera_id": d.camera_id,
        "geo_marker_id": d.geo_marker_id,
        "detection_type": d.detection_type,
        "confidence_score": d.confidence_score,
        "object_image": d.object_image,
        "numberplate_image": d.numberplate_image,
        "numberplate_text": d.numberplate_text,
        "person_image": d.person_image,
        "track_id": d.track_id,
        "timestamp": d.timestamp.isoformat(),
        "status": d.status
    } for d in detections]

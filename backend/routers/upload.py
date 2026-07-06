from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.database import get_db
from models.models import Camera
from schemas.schemas import Camera as CameraSchema
from auth.auth import get_current_user
import os
import shutil
import subprocess
import sys
from pathlib import Path

from app.process_manager import start_process

router = APIRouter()

# Media directory
MEDIA_DIR = Path(__file__).parent.parent / "media"
MEDIA_DIR.mkdir(exist_ok=True)

def start_detection_process(camera_id: int, video_path: str):
    """
    Background function to start detection process
    """
    if os.path.exists("/app/ai_engine"):
        project_root = Path("/app")
        log_file_path = project_root / "detection_service.log"
    else:
        project_root = Path(__file__).resolve().parent.parent.parent
        log_file_path = project_root / "backend" / "detection_service.log"
    
    script_path = project_root / "ai_engine" / "detection_service.py"
    
    try:
        # Prepare environment
        env = os.environ.copy()
        env["PYTHONPATH"] = str(project_root) + os.pathsep + env.get("PYTHONPATH", "")
        
        # Open log file in append mode. ProcessManager will use this.
        # We use a with statement or ensure it's closed if start_process fails.
        log_file = open(log_file_path, "a")
        try:
            log_file.write(f"\n--- Starting detection for camera {camera_id} at {Path(video_path).name} ---\n")
            log_file.flush()
            
            # Use ProcessManager to start and track the process
            start_process(
                camera_id=camera_id,
                command=[sys.executable, "-u", str(script_path), str(video_path), str(camera_id)],
                stdout=log_file,
                stderr=log_file,
                cwd=str(project_root),
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            print(f"✓ Started detection process for camera {camera_id}: {video_path}")
            print(f"  Logs available at: {log_file_path}")
        except Exception:
            log_file.close()
            raise
    except Exception as e:
        print(f"✗ Error starting detection process: {e}")

@router.post("/video", response_model=CameraSchema)
async def upload_video(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """
    Upload a video file and automatically:
    1. Save to backend/media directory
    2. Add camera entry
    3. Start automatic detection process
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    # Check if it's a video file
    allowed_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm'}
    file_ext = Path(file.filename).suffix.lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Generate safe filename
    safe_filename = file.filename.replace(" ", "_")
    file_path = MEDIA_DIR / safe_filename
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error saving file: {str(e)}")
    
    # Check if camera already exists with this filename
    existing_camera = db.query(Camera).filter(Camera.source == safe_filename).first()
    if existing_camera:
        # Update existing camera to active
        existing_camera.status = True
        db.commit()
        db.refresh(existing_camera)
        camera = existing_camera
    else:
        # Create new camera entry
        camera = Camera(
            type=2,  # MP4 file
            source=safe_filename,
            status=True
        )
        db.add(camera)
        db.commit()
        db.refresh(camera)
    
    # Start background detection task
    background_tasks.add_task(start_detection_process, camera.id, str(file_path))
    
    return camera


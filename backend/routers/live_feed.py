import cv2
import time
import numpy as np
import torch
import os
import sys
from jose import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from models.models import Camera, GeoMarker
from auth.auth import get_current_user
from ultralytics import YOLO
from pathlib import Path

# Add project root to sys.path to allow importing from ai_engine
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.append(project_root)

from ai_engine.geo_fence_utils import check_in_geo_fence, draw_geo_fences, draw_detections, draw_plate_highlight
from ai_engine.image_utils import get_enhancement_variants, upscale_image
from ai_engine.anpr_processor import AnprProcessor

router = APIRouter()

# Global models cache to avoid reloading per request if possible
# Note: In a production environment, this should be handled by a worker or model server
MODELS = {
    "main": None,
    "plate": None,
    "reader": None,
    "device": 'cuda' if torch.cuda.is_available() else 'cpu'
}

def load_models():
    """Load AI models into global cache"""
    if MODELS["main"] is None:
        try:
            # Main YOLO model - Upgrade to X (Extra Large) for maximum precision
            # Force path to be relative to backend directory to avoid multi-process conflicts
            model_path = str(Path(__file__).parent.parent / 'yolov8x.pt')
            MODELS["main"] = YOLO(model_path).to(MODELS["device"])
            print(f"✓ High-Precision YOLOv8x model loaded on {MODELS['device']}")
        except Exception as e:
            print(f"Error loading main YOLO model: {e}")

    if MODELS["plate"] is None:
        # Plate Model
        project_root = Path(__file__).parent.parent.parent
        local_model_path = project_root / "ai_engine" / "models" / "license_plate.pt"
        
        # Try local model first
        sources = [
            str(local_model_path),
            "keremberke/yolov8n-license-plate-detection",  # Known Hub model
            "keremberke/yolov8m-license-plate-detection"   # Higher precision medium model
        ]
        
        for source in sources:
            try:
                if source.endswith(".pt") and not os.path.exists(source): continue
                MODELS["plate"] = YOLO(source).to(MODELS["device"])
                print(f"✓ Plate model loaded from: {source}")
                break
            except:
                continue
    
    # NEW: Nozzle Detection Model (Specialized)
    if MODELS.get("nozzle") is None:
        try:
            # Roboflow / Hub model for nozzles
            # Using a known nozzle detector for high-precision
            nozzle_name = "keremberke/yolov8n-fuel-nozzle-detection"
            MODELS["nozzle"] = YOLO(nozzle_name).to(MODELS["device"])
            print(f"✓ Specialized Nozzle model loaded")
        except:
            print("⚠ Specialized nozzle model fallback to main detector")
            MODELS["nozzle"] = None
    
    if MODELS["reader"] is None:
        try:
            import pytesseract
            from PIL import Image
            
            # Configure Tesseract path
            tesseract_paths = [
                r'C:\Program Files\Tesseract-OCR\tesseract.exe',
                r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
                r'C:\Tesseract-OCR\tesseract.exe'
            ]
            
            for path in tesseract_paths:
                if os.path.exists(path):
                    pytesseract.pytesseract.tesseract_cmd = path
                    break
            
            # Test Tesseract
            test_version = pytesseract.get_tesseract_version()
            MODELS["reader"] = pytesseract
            print(f"✓ Tesseract OCR initialized for live feed (version: {test_version})")
        except Exception as e:
            print(f"⚠ Failed to initialize Tesseract: {e}")
            MODELS["reader"] = None

def refine_plate_text(text):
    """Refine plate text based on common patterns and misreads"""
    if not text: return None
    L2N = {'I': '1', 'L': '1', 'T': '7', 'B': '8', 'S': '5', 'G': '6', 'Z': '2', 'O': '0', 'Q': '0', 'D': '0'}
    N2L = {'0': 'O', '1': 'I', '2': 'Z', '5': 'S', '8': 'B'}
    
    # Standardize to uppercase and strip common noise
    text = text.upper().replace(" ", "").replace("POLICE", "")
    if len(text) < 3: return text

    # Indian Plate Pattern (e.g., TS09PA2069)
    if len(text) >= 7 and text[0:2].isalpha():
        res = list(text)
        for i in [2, 3]:
            if i < len(res) and res[i] in L2N: res[i] = L2N[res[i]]
        for i in range(len(res)-4, len(res)):
            if i >= 0 and res[i] in L2N: res[i] = L2N[res[i]]
        return "".join(res)

    if len(text) == 7:
        res = list(text)
        for i in [2, 3]:
            if res[i] in L2N: res[i] = L2N[res[i]]
        for i in [0, 1, 4, 5, 6]:
            if res[i].isdigit() and res[i] in N2L: res[i] = N2L[res[i]]
        return "".join(res)
    return text

def clean_plate_text(text):
    if not text: return None
    import re
    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
    refined = refine_plate_text(cleaned)
    # Basic length check for plates (e.g. at least 3 chars)
    if refined and len(refined) >= 3:
        return refined
    return None

def generate_frames(camera_id: int, camera_source: str, db: Session):
    """Generator for MJPEG stream with detection and geo-fencing"""
    load_models()
    
    # Check if RTSP or local file
    is_rtsp = camera_source.lower().startswith('rtsp://')
    if not is_rtsp and not os.path.isabs(camera_source):
        # Assume it's a media file in backend/media
        media_dir = Path(__file__).parent.parent / "media"
        camera_source = str(media_dir / camera_source)

    cap = cv2.VideoCapture(camera_source)
    if not cap.isOpened():
        print(f"Failed to open source: {camera_source}")
        return

    # Trackers for the session
    track_history = {} # track_id -> {'best_plate': str, 'best_plate_conf': float, 'ocr_count': int, 'consensus_reached': bool}
    anpr_processor = AnprProcessor(buffer_size=20, min_votes=3)  # Updated parameters
    
    # Process every Nth frame for performance
    process_interval = 2
    frame_count = 0
    
    # Fetch geo-fences
    geo_fences = db.query(GeoMarker).filter(GeoMarker.camera_id == camera_id).all()
    geo_fences_list = [{"id": m.id, "x1": m.x1, "y1": m.y1, "x2": m.x2, "y2": m.y2} for m in geo_fences]

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            if frame_count % process_interval != 0:
                # Just draw previous/overlay or skip
                # For MJPEG we can skip or show last frame to keep FPS high
                # Here we continue to yield a JPEG to maintain the stream
                pass
            else:
                # 4K PERFORMANCE OPTIMIZATION:
                # Downscale high-res frames for tracking to save GPU load
                width = frame.shape[1]
                tracking_frame = frame
                track_scale = 1.0
                if width > 1920:
                    track_scale = 1280.0 / width
                    tracking_frame = cv2.resize(frame, (1280, int(frame.shape[0] * track_scale)))
                
                # Run Main Detection (Track Humans, Cars, Trucks, Bikes)
                results_main = MODELS["main"].track(tracking_frame, persist=True, device=MODELS["device"], verbose=False)
                
                # Run Specialized Nozzle Detection if available
                nozzle_results = []
                if MODELS.get("nozzle"):
                    try:
                        nozzle_results = MODELS["nozzle"](tracking_frame, conf=0.25, verbose=False)
                    except:
                        pass
                
                # Draw Geo-Fences first
                draw_geo_fences(frame, geo_fences_list)
                
                # Combine results
                all_results = results_main
                
                for result in all_results:
                    if result.boxes is None: continue
                    
                    boxes = result.boxes.xyxy.cpu().numpy().astype(int)
                    track_ids = result.boxes.id.cpu().numpy().astype(int) if result.boxes.id is not None else [None] * len(boxes)
                    clss = result.boxes.cls.cpu().numpy().astype(int)
                    
                    # Process main detections
                    for box, track_id, cls in zip(boxes, track_ids, clss):
                        class_name = MODELS["main"].names[cls].lower()
                        
                        detection_type = None
                        if class_name in ['car', 'truck', 'bus', 'motorcycle', 'bicycle', 'person']:
                            mapping = {'car': 'Car', 'truck': 'Truck', 'bus': 'Truck', 'motorcycle': 'Bike', 'bicycle': 'Bike', 'person': 'Human'}
                            detection_type = mapping[class_name]
                        
                        if not detection_type: continue
                        
                        # High-Precision ROI Check - Scale back to original dimensions
                        check_box = box
                        if track_scale != 1.0:
                            check_box = [int(box[0] / track_scale), int(box[1] / track_scale), int(box[2] / track_scale), int(box[3] / track_scale)]
                        
                        geo_marker_id = check_in_geo_fence(check_box, geo_fences_list)
                        in_fence = geo_marker_id is not None
                        
                        # Process Nozzle results in parallel for the same frame
                        # If a nozzle is found, it will be added to the visualization
                        # through the loop below (we process nozzles separately)
                        
                        # ANPR and visualization follows...
                        
                        # Create/Get track record
                        if track_id is not None and track_id not in track_history:
                            track_history[track_id] = {'best_plate': None, 'conf': 0, 'ocr_count': 0, 'consensus_reached': False}
                        current_record = track_history.get(track_id, {'best_plate': None, 'conf': 0, 'ocr_count': 0, 'consensus_reached': False})
                        
                        plate_text = None
                        
                        # ANPR Logic with Performance Throttling
                        do_ocr = False
                        if detection_type in ['Car', 'Truck', 'Bike'] and MODELS["plate"] and MODELS["reader"]:
                            current_record['ocr_count'] += 1
                            if not current_record['consensus_reached'] or current_record['ocr_count'] % 10 == 0:
                                if current_record['ocr_count'] == 1 or current_record['ocr_count'] % 3 == 0:
                                    do_ocr = True

                        if do_ocr:
                            # Map box from tracking scale back to original resolution if needed
                            x1, y1, x2, y2 = box
                            if track_scale != 1.0:
                                x1_orig = int(x1 / track_scale)
                                y1_orig = int(y1 / track_scale)
                                x2_orig = int(x2 / track_scale)
                                y2_orig = int(y2 / track_scale)
                            else:
                                x1_orig, y1_orig, x2_orig, y2_orig = x1, y1, x2, y2
                            
                            object_crop = frame[y1_orig:y2_orig, x1_orig:x2_orig].copy()
                                
                            if object_crop.size > 0:
                                # Enhancement: High-res crop for plate detector
                                h, w = object_crop.shape[:2]
                                scale_factor = 1.0
                                if w < 400: scale_factor = 2.0
                                elif w < 800: scale_factor = 1.5
                                
                                object_image_detector = cv2.resize(object_crop, (int(w * scale_factor), int(h * scale_factor)), interpolation=cv2.INTER_CUBIC)
                                plate_results = MODELS["plate"](object_image_detector, conf=0.20, verbose=False)
                                    
                                # Initialize variables
                                plate_text = None
                                consensus_text = None
                                    
                                for p_res in plate_results:
                                    if p_res.boxes is None: continue
                                    for p_box in p_res.boxes:
                                        px1, py1, px2, py2 = p_box.xyxy[0].cpu().numpy().astype(int)
                                        p_conf_val = float(p_box.conf[0])
                                        
                                        # IMPORTANT: Extract the crop from the upscaled image
                                        plate_crop = object_image_detector[py1:py2, px1:px2].copy()
                                        
                                        # Draw plate highlight (convert to global coordinates, adjusting for scale and car position)
                                        # x1_orig/y1_orig are the car's top-left in the 4K frame
                                        global_plate_box = [
                                            int(px1 / scale_factor) + x1_orig, 
                                            int(py1 / scale_factor) + y1_orig, 
                                            int(px2 / scale_factor) + x1_orig, 
                                            int(py2 / scale_factor) + y1_orig
                                        ]
                                        
                                        # Multi-Pass OCR Enhancement
                                        variants = get_enhancement_variants(plate_crop)
                                        
                                        best_clean_text = None
                                        best_ocr_conf = 0
                                        
                                        for i, variant in enumerate(variants):
                                            # PaddleOCR returns: [[[box], (text, confidence)]]
                                            try:
                                                ocr_results = MODELS["reader"].ocr(variant, cls=True)
                                                if not ocr_results or not ocr_results[0]:
                                                    continue
                                                
                                                # Extract text and confidence
                                                texts = []
                                                confidences = []
                                                for line in ocr_results[0]:
                                                    if line and len(line) >= 2:
                                                        text, conf = line[1]
                                                        if conf > 0.10:
                                                            texts.append(text)
                                                            confidences.append(conf)
                                                
                                                if not texts:
                                                    continue
                                                    
                                                found_text = "".join(texts)
                                                clean_text_v = clean_plate_text(found_text)
                                                
                                                if clean_text_v:
                                                    v_conf = sum(confidences) / len(confidences)
                                                    if v_conf > best_ocr_conf:
                                                        best_ocr_conf = v_conf
                                                        best_clean_text = clean_text_v
                                            except Exception as ocr_err:
                                                continue
                                        
                                        consensus_text = None
                                        if best_clean_text:
                                            # Use temporal consensus
                                            consensus_text = anpr_processor.add_prediction(track_id, best_clean_text, p_conf_val)
                                            plate_text = consensus_text or best_clean_text
                                            if consensus_text and v_conf > 0.8:
                                                current_record['consensus_reached'] = True
                                        
                                        # STRICT FILTERING:
                                        # 1. Size Check: Plate shouldn't be too large relative to vehicle (likely body text)
                                        # 2. Blacklist Check (Strip 'POLICE' in refinement)
                                        is_false_positive = False
                                        
                                        # 1. Aspect Ratio Check (Plates are rectangular or square-ish)
                                        pw, ph = (px2 - px1), (py2 - py1)
                                        aspect_ratio = pw / float(ph) if ph > 0 else 0
                                        
                                        # 2. Area ratio check (plate area / vehicle area)
                                        # Use actual dimensions of the resized detector image
                                        h_det, w_det = object_image_detector.shape[:2]
                                        vehicle_area_det = h_det * w_det
                                        plate_area = pw * ph
                                        area_ratio = plate_area / vehicle_area_det
                                        
                                        # RELAXED Filtering for better recall:
                                        # - Aspect ratio: 0.8 to 8.0
                                        # - Area ratio: 0.1% to 40%
                                        if aspect_ratio < 0.8 or aspect_ratio > 8.0:
                                            is_false_positive = True
                                        elif area_ratio < 0.001 or area_ratio > 0.40:
                                            is_false_positive = True

                                        if (consensus_text or best_clean_text) and not is_false_positive:
                                            plate_text = consensus_text or best_clean_text
                                            # Draw ONLY the plate highlight, not the vehicle box
                                            draw_plate_highlight(frame, global_plate_box, plate_text)
                                            
                                            # Update track history if we have track_id
                                            if track_id is not None:
                                                if track_id not in track_history or p_conf_val > track_history[track_id].get('conf', 0):
                                                    track_history[track_id] = {'best_plate': plate_text, 'conf': p_conf_val}
                                            break # Found a plate
                                        elif not is_false_positive:
                                            # Draw plate box even if OCR hasn't succeeded yet
                                            draw_plate_highlight(frame, global_plate_box)
                                if plate_text: break # Found a plate for this vehicle
                        
                        # Use cached plate text if not found in this frame but exists in history
                        if not plate_text and track_id is not None and track_id in track_history:
                            plate_text = track_history[track_id].get('best_plate')
                            
                        # Draw detection
                        # Always draw vehicle box UNLESS we have a stable plate (consensus)
                        # This ensures the user sees something is happening even if OCR is slow
                        has_stable_plate = track_id is not None and anpr_processor.is_stable(track_id)
                        
                        # Always draw detection box (Premium style)
                        # Map box from tracking scale back to original resolution for drawing
                        draw_box = box
                        if track_scale != 1.0:
                            draw_box = [int(box[0] / track_scale), int(box[1] / track_scale), int(box[2] / track_scale), int(box[3] / track_scale)]
                        
                        draw_detections(frame, draw_box, detection_type, track_id, plate_text, in_fence)
                
                # Draw Specialized Nozzles (Only if specialized model is loaded)
                if MODELS.get("nozzle"):
                    for n_res in nozzle_results:
                        if n_res.boxes is None: continue
                        n_boxes = n_res.boxes.xyxy.cpu().numpy().astype(int)
                        n_confs = n_res.boxes.conf.cpu().numpy().astype(float)
                        for n_box, n_conf in zip(n_boxes, n_confs):
                            # Scale box to original resolution for drawing on 4K/standard frame
                            draw_n_box = n_box
                            if track_scale != 1.0:
                                draw_n_box = [int(n_box[0] / track_scale), int(n_box[1] / track_scale), int(n_box[2] / track_scale), int(n_box[3] / track_scale)]
                            
                            n_geo_id = check_in_geo_fence(draw_n_box, geo_fences_list)
                            draw_detections(frame, draw_n_box, "Fuel Nozzle", None, None, n_geo_id is not None)

            # Encode frame as JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            if not ret:
                continue
                
            frame_bytes = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
            
            # Small sleep to control FPS if it's too fast (for files)
            if not is_rtsp:
                time.sleep(0.01)

    except Exception as e:
        print(f"Error in stream generation: {e}")
    finally:
        cap.release()

@router.get("/{camera_id}")
async def live_feed(camera_id: int, token: str = None, db: Session = Depends(get_db)):
    """Endpoint for live MJPEG stream"""
    # Simple token validation if passed via query
    if token:
        from auth.auth import SECRET_KEY, ALGORITHM
        from jose import jwt
        try:
            jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        except:
            raise HTTPException(status_code=401, detail="Invalid token")
    else:
        # Fallback to standard dependency if no query token
        # But for <img> tag we MUST have it in query or session
        # For simplicity in this demo, we'll allow it if token is provided
        pass

    camera = db.query(Camera).filter(Camera.id == camera_id).first()
    if not camera:
        raise HTTPException(status_code=404, detail="Camera not found")
    
    return StreamingResponse(
        generate_frames(camera_id, camera.source, db),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )

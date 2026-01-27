#!/usr/bin/env python3
"""
Video detection service that processes video and sends detections to backend.
This script uses YOLO to detect objects (including Fuel Nozzles) and vehicles,
and performs OCR on vehicle license plates.

Usage:
    python detection_service.py [video_path] [camera_id]
"""

import sys
import cv2
import time
import numpy as np
from datetime import datetime
from ai_engine.backend_integration import BackendIntegration
from ai_engine.geo_fence_utils import check_in_geo_fence
from ultralytics import YOLO
import easyocr
import re
import logging
import os
from ai_engine.image_utils import get_enhancement_variants, upscale_image
from ai_engine.anpr_processor import AnprProcessor
from pathlib import Path

# Configure logging to stdout so it's captured by the backend
logging.basicConfig(
    stream=sys.stdout,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Detection type mapping from YOLO classes to our types
# Standard YOLOv8 classes (COCO dataset)
CLASS_MAPPING = {
    'car': 'Car',
    'truck': 'Truck',
    'bus': 'Truck',
    'motorcycle': 'Bike',
    'person': 'Human',
}

# Custom classes (if present in custom model)
CUSTOM_MAPPING = {
    'nozzle': 'Fuel Nozzle',
    'fuel_nozzle': 'Fuel Nozzle',  # Alternative name
}

def refine_plate_text(text):
    """Refine plate text based on common patterns and misreads"""
    if not text: return None
    
    # Common OCR substitutions (Letter -> Number)
    L2N = {'I': '1', 'L': '1', 'T': '7', 'B': '8', 'S': '5', 'G': '6', 'Z': '2', 'O': '0', 'Q': '0', 'D': '0'}
    # Number -> Letter
    N2L = {'0': 'O', '1': 'I', '2': 'Z', '5': 'S', '8': 'B'}
    
    # Standardize to uppercase and strip common noise
    text = text.upper().replace(" ", "").replace("POLICE", "")
    
    # Shorten text if it's very short
    if len(text) < 3: return text
    
    # Indian Plate Pattern (e.g., TS09PA2069)
    # Format: [State:AA] [Dist:NN] [Series:AA] [Num:NNNN] -> 8-10 chars
    # or [State:AA] [Dist:NN] [Num:NNNN] -> 7-8 chars
    if len(text) >= 7 and text[0:2].isalpha():
        res = list(text)
        # Position 2 and 3 should be digits (District)
        for i in [2, 3]:
            if i < len(res) and res[i] in L2N: res[i] = L2N[res[i]]
        # Last 4 should be digits
        for i in range(len(res)-4, len(res)):
            if i >= 0 and res[i] in L2N: res[i] = L2N[res[i]]
        return "".join(res)

    # UK-Specific Pattern (e.g., NA13 NRU -> NA13NRU)
    # Format: [AA] [NN] [AAA] (7 chars)
    if len(text) == 7:
        res = list(text)
        for i in [2, 3]:
            if res[i] in L2N: res[i] = L2N[res[i]]
        for i in [0, 1, 4, 5, 6]:
            if res[i].isdigit() and res[i] in N2L: res[i] = N2L[res[i]]
        return "".join(res)
    
    return text

def clean_plate_text(text):
    """Clean and validate plate text"""
    if not text: return None
    # Remove non-alphanumeric characters
    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
    
    # Apply pattern-based refinement
    refined = refine_plate_text(cleaned)
    
    # Basic length check for plates (e.g. at least 3 chars)
    if refined and len(refined) >= 3:
        return refined
    return None

def detect_objects_in_video(video_path, camera_id=None):
    """Process video using advanced tracking and send detections to backend"""
    
    # Initialize backend integration
    logging.info("Starting advanced detection service...")
    print("Connecting to backend...")
    backend = BackendIntegration()
    
    if not backend.auth_token:
        msg = "✗ Failed to authenticate with backend"
        print(msg)
        logging.error(msg)
        return
    
    logging.info("Connected to backend")
    print("✓ Connected to backend")
    
    # Detect device - Force CUDA if possible
    import torch
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    if device == 'cpu':
        logging.warning("🚀 CUDA not available, using CPU. Performance will be LIMITED on 4K video.")
    else:
        logging.info(f"🚀 Using CUDA acceleration: {torch.cuda.get_device_name(0)}")
    print(f"🚀 Using device: {device}")
    
    # Load Models
    print("Loading models...")
    logging.info("Loading models...")
    
    # 1. Main Object Detector (YOLO)
    try:
        # Use YOLOv8x for maximum precision in detection
        # Point to backend folder where we know it's downloaded
        project_root = Path(__file__).parent.parent
        model_path = str(project_root / 'backend' / 'yolov8x.pt')
        model = YOLO(model_path).to(device) 
        logging.info(f"✓ High-Precision YOLOv8x model loaded from: {model_path}")
        print(f"✓ High-Precision YOLOv8x model loaded")
    except Exception as e:
        msg = f"✗ Failed to load YOLO model: {e}"
        print(msg)
        logging.error(msg)
        return

    # 2. License Plate Detector (YOLO)
    print("Loading license plate detection model...")
    try:
        # Priority order for plate models
        local_model_path = os.path.join(os.path.dirname(__file__), "models", "license_plate.pt")
        
        model_sources = []
        
        # 1. Check for local model first
        model_sources = []
        
        # 1. Check for local model first - High Accuracy Hugging Face Model
        if os.path.exists(local_model_path):
            model_sources.append(("Local High-Accuracy Model", local_model_path))
        
        # 2. Try known working hub models (formatted for YOLO hub download)
        model_sources.extend([
            ("Hugging Face Hub", "keremberke/yolov8n-license-plate-detection"),
            ("Roboflow Hub", "keremberke/yolov8n-license-plate"),
        ])
        
        plate_model = None
        for source_name, model_path in model_sources:
            try:
                logging.info(f"Attempting to load plate model from {source_name}: {model_path}")
                test_model = YOLO(model_path).to(device)
                
                # Check if it was a successful hub download or file load
                if test_model is not None:
                    # Verify if this model has plate-related classes
                    model_classes = [n.lower() for n in test_model.names.values()]
                    class_str = " ".join(model_classes)
                    
                    if any(keyword in class_str for keyword in ['plate', 'license', 'lp', 'number']):
                        plate_model = test_model
                        logging.info(f"✓ Valid Plate model loaded from {source_name}")
                        print(f"✓ License Plate model loaded: {source_name}")
                        break
                    else:
                        logging.warning(f"  {source_name} does not contain plate classes. Skipping.")
            except Exception as e:
                logging.warning(f"  Failed to load from {source_name}: {e}")
        
        if not plate_model:
            logging.warning("✗ No specialized plate model found. Using OCR-only mode.")
            print("⚠ No specialized plate model - using OCR-only mode")
            print("  For better accuracy, run: python ai_engine/download_plate_model.py")
    except Exception as e:
        logging.warning(f"⚠ Critical failure in plate model loading: {e}")
        plate_model = None

    # 3. Nozzle Detector (Specialized)
    print("Loading specialized nozzle detection model...")
    try:
        # Load high-precision nozzle detector from Hub
        nozzle_model = YOLO("keremberke/yolov8n-fuel-nozzle-detection").to(device)
        logging.info("✓ Specialized Nozzle model loaded")
        print("✓ Specialized Nozzle model loaded")
    except Exception as e:
        logging.warning(f"⚠ Failed to load specialized nozzle model: {e}")
        nozzle_model = None

    # 4. OCR Reader
    print("Initializing OCR...")
    try:
        # Force GPU and use allowlist for cleaner results
        reader = easyocr.Reader(['en'], gpu=(device == 'cuda'), verbose=False)
        # Add allowlist to the reader processing if we were calling it here, 
        # but we use it in the loop. 
        logging.info(f"✓ OCR initialized (GPU: {device == 'cuda'})")
        print(f"✓ OCR initialized (GPU: {device == 'cuda'})")
    except Exception as e:
        logging.warning(f"⚠ Failed to initialize OCR: {e}")
        print(f"⚠ Failed to initialize OCR: {e}")
        reader = None
    
    # Open video
    logging.info(f"Opening video: {video_path}")
    
    # Check if it's an RTSP stream
    is_rtsp = video_path.lower().startswith('rtsp://')
    
    if is_rtsp:
        # RTSP stream - use specific options for better compatibility
        cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
        # Set buffer size to reduce latency
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        logging.info(f"Opening RTSP stream: {video_path}")
    else:
        # Regular video file
        cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        error_msg = f"✗ Failed to open video: {video_path}"
        if is_rtsp:
            error_msg += "\n  RTSP connection failed. Check:"
            error_msg += "\n  - Camera is online and accessible"
            error_msg += "\n  - RTSP URL is correct (rtsp://username:password@ip:port/stream)"
            error_msg += "\n  - Network connectivity"
            error_msg += "\n  - Firewall settings"
        print(error_msg)
        logging.error(error_msg)
        return
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    
    # For RTSP streams, FPS might be 0 or unreliable
    if fps == 0 or is_rtsp:
        fps = 30  # Default to 30 FPS for RTSP
        logging.info(f"Using default FPS: {fps} for RTSP stream")
    
    stream_type = "RTSP stream" if is_rtsp else "video file"
    print(f"✓ {stream_type.capitalize()} opened: {width}x{height} @ {fps}fps")
    logging.info(f"Video opened: {width}x{height} @ {fps}fps (Type: {stream_type})")
    
    # Trackers and persistence
    track_history = {} # track_id -> { 'type': str, 'best_plate': str, 'last_sent': float, 'ocr_count': int, 'consensus_reached': bool }
    anpr_processor = AnprProcessor(buffer_size=10, min_votes=2)
    
    frame_count = 0
    process_interval = 2 # process every 2nd frame for speed but keep tracking
    
    print("\n" + "=" * 60)
    print("Processing video with TRACKING... (Press Ctrl+C to stop)")
    print("=" * 60)
    
    # Update camera status to processing
    if camera_id:
        backend.update_camera_processing_status(camera_id, "processing")
    
    # Fetch geo-fences for this camera
    geo_fences = []
    if camera_id:
        try:
            geo_fences = backend.get_geo_markers(camera_id)
            if geo_fences:
                print(f"  Loaded {len(geo_fences)} geo-fences for camera {camera_id}")
        except Exception as e:
            print(f"  Warning: Could not fetch geo-fences: {e}")
    
    
    # Statistics tracking
    total_detections_sent = 0
    start_time = time.time()
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                # Video has ended
                print("\n" + "=" * 60)
                print("✓ VIDEO PROCESSING COMPLETE")
                print("=" * 60)
                elapsed_time = time.time() - start_time
                print(f"  Total frames processed: {frame_count}")
                print(f"  Total unique objects tracked: {len(track_history)}")
                print(f"  Processing time: {elapsed_time:.2f} seconds")
                print(f"  Average FPS: {frame_count/elapsed_time:.2f}")
                print("=" * 60)
                logging.info(f"Video processing complete. Processed {frame_count} frames in {elapsed_time:.2f}s")
                
                # Update camera status to completed
                if camera_id:
                    completion_msg = (
                        f"Video processing completed successfully. "
                        f"Processed {frame_count} frames in {elapsed_time:.2f}s. "
                        f"Tracked {len(track_history)} unique objects. "
                        f"Average FPS: {frame_count/elapsed_time:.2f}"
                    )
                    backend.update_camera_processing_status(camera_id, "completed", completion_msg)
                
                # Force immediate exit to stop all processing and threads
                print("\n✓ Detection service terminated gracefully")
                sys.exit(0)
            
            frame_count += 1
            if frame_count % process_interval != 0:
                continue
                
            # 4K PERFORMANCE OPTIMIZATION:
            # Downscale high-res frames for tracking/detection to save CPU/GPU
            tracking_frame = frame
            track_scale = 1.0
            if width > 1920:
                track_scale = 1280.0 / width
                tracking_frame = cv2.resize(frame, (1280, int(height * track_scale)))
                
            # Run Tracking
            try:
                # tracker='botsort.yaml' or 'bytetrack.yaml'
                results = model.track(tracking_frame, persist=True, device=device, verbose=False)
            except Exception as e:
                logging.error(f"Tracking error at frame {frame_count}: {e}")
                continue
            
            for result in results:
                if result.boxes is None or result.boxes.id is None:
                    continue
                
                try:
                    boxes = result.boxes.xyxy.cpu().numpy().astype(int)
                    track_ids = result.boxes.id.cpu().numpy().astype(int)
                    clss = result.boxes.cls.cpu().numpy().astype(int)
                    confs = result.boxes.conf.cpu().numpy().astype(float)
                except Exception as e:
                    logging.error(f"Error parsing tracking results: {e}")
                    continue
                
                for box, track_id, cls, conf in zip(boxes, track_ids, clss, confs):
                    class_name = model.names[cls].lower()
                    
                    # Determine detection type
                    detection_type = None
                    if class_name in CLASS_MAPPING:
                        detection_type = CLASS_MAPPING[class_name]
                    elif class_name in CUSTOM_MAPPING:
                        detection_type = CUSTOM_MAPPING[class_name]
                    elif 'nozzle' in class_name or 'fuel' in class_name:
                        detection_type = 'Fuel Nozzle'
                    
                    if not detection_type:
                        continue
                    
                    x1, y1, x2, y2 = box
                    object_image = frame[y1:y2, x1:x2].copy()
                    
                    # Initialize or get from history
                    if track_id not in track_history:
                        track_history[track_id] = {
                            'type': detection_type,
                            'best_plate': None,
                            'last_sent': 0,
                            'best_plate_conf': 0,
                            'ocr_count': 0,
                            'consensus_reached': False
                        }
                    
                    current_record = track_history[track_id]
                    should_send = False
                    
                    # ANPR Logic with Performance Throttling
                    # 1. Only process vehicles
                    # 2. Only run OCR if consensus not reached or periodically
                    do_ocr = False
                    if detection_type in ['Car', 'Truck', 'Bike'] and plate_model and reader:
                        # Throttle OCR: Run first frame always, then every 3rd
                        current_record['ocr_count'] += 1
                        if not current_record['consensus_reached'] or current_record['ocr_count'] % 10 == 0:
                            if current_record['ocr_count'] == 1 or current_record['ocr_count'] % 3 == 0:
                                do_ocr = True
                    
                    if do_ocr:
                        # Map box from tracking scale back to original resolution if needed
                        if track_scale != 1.0:
                            x1_orig = int(x1 / track_scale)
                            y1_orig = int(y1 / track_scale)
                            x2_orig = int(x2 / track_scale)
                            y2_orig = int(y2 / track_scale)
                        else:
                            x1_orig, y1_orig, x2_orig, y2_orig = x1, y1, x2, y2
                            
                        object_image = frame[y1_orig:y2_orig, x1_orig:x2_orig].copy()
                            
                        if object_image.size > 0:
                            # Enhancement: Upscale small crops to improve detection
                            h, w = object_image.shape[:2]
                            scale_factor = 1.0
                            if w < 400: scale_factor = 2.0
                            elif w < 800: scale_factor = 1.5
                            
                            object_image_detector = cv2.resize(object_image, (int(w * scale_factor), int(h * scale_factor)), interpolation=cv2.INTER_CUBIC)

                            plate_results = plate_model(object_image_detector, conf=0.15, verbose=False)
                            
                            # Initialize detection variables for this object
                            best_text_to_use = None
                            avg_conf = conf # Use the vehicle confidence as the baseline
                            
                            for p_res in plate_results:
                                if p_res.boxes is None: continue
                                for p_box in p_res.boxes:
                                    px1, py1, px2, py2 = p_box.xyxy[0].cpu().numpy().astype(int)
                                    p_conf_val = float(p_box.conf[0])
                                    
                                    plate_crop = object_image_detector[py1:py2, px1:px2].copy()
                                    if plate_crop.size > 0:
                                        # Multi-Pass OCR Enhancement
                                        variants = get_enhancement_variants(plate_crop)
                                        
                                        best_clean_text = None
                                        best_ocr_conf = 0
                                        
                                        for i, variant in enumerate(variants):
                                            # Use allowlist to filter out noise
                                            ocr_results = reader.readtext(variant, allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ')
                                            found_text = " ".join([t for _, t, c in ocr_results if c > 0.15])
                                            clean_text = clean_plate_text(found_text)
                                            
                                            if clean_text:
                                                # Calculate confidence for this variant
                                                v_conf = sum([c for _, _, c in ocr_results if c > 0.15]) / (len(ocr_results) or 1)
                                                if i > 0:
                                                    logging.debug(f"  [Variant {i}] Succeeded: {clean_text} (conf: {v_conf:.2f})")
                                                if v_conf > best_ocr_conf:
                                                    best_ocr_conf = v_conf
                                                    best_clean_text = clean_text
                                        
                                        if best_clean_text == None:
                                            logging.debug(f"  [Track {track_id}] OCR Failed on all 4 variants")
                                        
                                        # Use AnprProcessor with the best found text
                                        if best_clean_text:
                                            # Add to temporal processor
                                            avg_conf = (p_conf_val + best_ocr_conf) / 2
                                            consensus_text = anpr_processor.add_prediction(track_id, best_clean_text, avg_conf)
                                            best_text_to_use = consensus_text or best_clean_text
                                            
                                            # If consensus is strong, mark it reached to slow down OCR
                                            if consensus_text and avg_conf > 0.8:
                                                current_record['consensus_reached'] = True
                                        else:
                                            # Keep record of failure for debugging if needed
                                            pass
                                        
                                        # STRICT FILTERING:
                                        # 1. Size Check: Plate shouldn't be too large relative to vehicle (likely body text)
                                        # 2. Blacklist Check (Simplified: We now strip 'POLICE' in refinement)
                                        is_false_positive = False
                                        
                                        # Area ratio check (plate area / vehicle area)
                                        # Adjust for scale factor used in detector
                                        plate_area = (px2 - px1) * (py2 - py1)
                                        vehicle_area_scaled = (x2 - x1) * (y2 - y1) * (scale_factor ** 2)
                                        
                                        if plate_area / vehicle_area_scaled > 0.40: # Extemely relaxed (40%)
                                            is_false_positive = True

                                        if best_text_to_use and not is_false_positive:
                                            # Update best plate info using consensus
                                            current_record['best_plate'] = best_text_to_use
                                            current_record['best_plate_conf'] = avg_conf
                                            current_record['plate_img'] = plate_crop
                                            should_send = True # found/updated info
                    
                    # Rate limit sending to backend (every 2 seconds or if we have a new best plate)
                    now = time.time()
                    # Only send if we updated the plate OR enough time has passed (to avoid flood)
                    if should_send or (now - current_record['last_sent'] > 2):
                        # Relaxed Filter:
                        # 1. If it's NOT a vehicle (e.g. Human), send it.
                        # 2. If it IS a vehicle, wait for a plate OR at least 3 OCR attempts
                        is_vehicle = detection_type in ['Car', 'Truck', 'Bike']
                        if not is_vehicle or current_record['best_plate'] or current_record['ocr_count'] > 3:
                            # Check if detection is within any geo-fence
                            bbox = [x1, y1, x2, y2]
                            geo_marker_id = check_in_geo_fence(bbox, geo_fences)
                            
                            detection_data = {
                                "detection_type": detection_type,
                                "camera_id": camera_id,
                                "track_id": track_id,
                                "confidence_score": conf,
                                "object_image": object_image,
                                "numberplate_text": current_record['best_plate'],
                                "numberplate_image": current_record.get('plate_img'),
                                "geo_marker_id": geo_marker_id
                            }
                            # Send detection and check for STOP signal (camera deleted)
                            result = backend.send_detection(detection_data)
                            if result == "STOP":
                                print("\n⚠ Camera deleted remotely. Stopping service.")
                                return

                            if result:
                                current_record['last_sent'] = now
                                total_detections_sent += 1
                                plate_info = current_record['best_plate'] or '-no plate-'
                                fence_info = f" [Geo-Fence: {geo_marker_id}]" if geo_marker_id else ""
                                logging.info(f"🚀 [Track {track_id}] {detection_type} Sent! Plate: {plate_info}{fence_info}")

            # NEW: Specialized Nozzle Detection for this Frame
            if nozzle_model:
                try:
                    # Run on tracking scale for speed, but adjust boxes later
                    n_results = nozzle_model(tracking_frame, conf=0.25, verbose=False)
                    for n_res in n_results:
                        if n_res.boxes is None: continue
                        n_boxes = n_res.boxes.xyxy.cpu().numpy().astype(int)
                        n_confs = n_res.boxes.conf.cpu().numpy().astype(float)
                        
                        for n_box, n_conf in zip(n_boxes, n_confs):
                            # Map to original resolution
                            if track_scale != 1.0:
                                x1_n, y1_n, x2_n, y2_n = (n_box / track_scale).astype(int)
                            else:
                                x1_n, y1_n, x2_n, y2_n = n_box
                            
                            n_crop = frame[y1_n:y2_n, x1_n:x2_n].copy()
                            if n_crop.size == 0: continue
                            
                            n_geo_id = check_in_geo_fence([x1_n, y1_n, x2_n, y2_n], geo_fences)
                            
                            # Send Nozzle Detection
                            n_data = {
                                "detection_type": "Fuel Nozzle",
                                "camera_id": camera_id,
                                "confidence_score": n_conf,
                                "object_image": n_crop,
                                "geo_marker_id": n_geo_id
                            }
                            backend.send_detection(n_data)
                            logging.info(f"🚀 [Nozzle] Fuel Nozzle Detected & Sent! {f'[Geo: {n_geo_id}]' if n_geo_id else ''}")
                except Exception as e:
                    logging.error(f"Nozzle detection error: {e}")

            # No visualization in background
                
    except KeyboardInterrupt:
        print("\n" + "=" * 60)
        print("⚠ PROCESSING STOPPED BY USER")
        print("=" * 60)
        elapsed_time = time.time() - start_time
        print(f"  Frames processed: {frame_count}")
        print(f"  Unique objects tracked: {len(track_history)}")
        print(f"  Processing time: {elapsed_time:.2f} seconds")
        print("=" * 60)
        logging.info(f"Processing stopped by user at frame {frame_count}")
        sys.exit(0)
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("\n✓ Detection service terminated gracefully")

def main():
    if len(sys.argv) < 2:
        print("Usage: python detection_service.py <video_path> [camera_id]")
        return
    
    video_path = sys.argv[1]
    camera_id = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    if not os.path.exists(video_path):
        print(f"✗ File not found: {video_path}")
        return
        
    detect_objects_in_video(video_path, camera_id)

if __name__ == "__main__":
    main()

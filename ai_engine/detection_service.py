#!/usr/bin/env python3
"""
Advanced AI Detection Service with YOLO Tracking + Tesseract OCR
"""

import os
import sys
import cv2
import numpy as np
import torch
import logging
from ultralytics import YOLO
import requests
import base64
import time
import re
from collections import defaultdict
from ai_engine.backend_integration import BackendIntegration
from ai_engine.geo_fence_utils import check_in_geo_fence
from ai_engine.image_utils import get_enhancement_variants
from ai_engine.anpr_processor import AnprProcessor
from pathlib import Path

# Configure logging to write to both file and stdout with UTF-8 encoding
if os.path.exists('/app/ai_engine'):
    log_file = '/app/detection_service.log'
else:
    log_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'backend', 'detection_service.log')

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)8s] %(filename)s:%(lineno)d - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),  # UTF-8 for emojis
        logging.StreamHandler(sys.stdout)
    ]
)

# Detection type mapping from YOLO classes to our types
# Standard YOLOv8 classes (COCO dataset)
CLASS_MAPPING = {
    'car': 'Car',
    'truck': 'Truck',
    'bus': 'Truck',
    'motorcycle': 'Bike',
    'bicycle': 'Bike',
    'person': 'Human',
}

# Custom classes (if present in custom model)
CUSTOM_MAPPING = {
    'nozzle': 'Fuel Nozzle',
    'fuel_nozzle': 'Fuel Nozzle',  # Alternative name
}

def refine_plate_text(text):
    """
    Refine OCR text with common corrections for Indian license plates.
    Fixes typical OCR errors while avoiding over-correction.
    Indian plate format: XX00XX0000 (e.g., TS09PAZ063)
    """
    if not text or len(text) < 3:
        return text
    
    # Remove common noise patterns
    noise_patterns = ["POLICE", "GOVT", "TAXI", "AMBULANCE"]
    for noise in noise_patterns:
        text = text.replace(noise, "")
    
    if len(text) < 8:  # Too short to be a valid plate
        return text
    
    # Indian plate structure: XX 00 XX 0000
    # Positions: 0-1 (state), 2-3 (district), 4-6/7 (series), rest (number)
    
    # Common OCR corrections for numbers
    corrections_numeric = {
        'O': '0',  # Letter O to number 0
        'I': '1',  # Letter I to number 1
        'S': '5',  # Letter S to number 5 (but not always - could be in series)
        'Z': '2',  # Letter Z to number 2
        'B': '8',  # Letter B to number 8
        'G': '6',  # Letter G to number 6
    }
    
    refined = ""
    for i, char in enumerate(text):
        # Positions 0-1: State code (always letters) - keep as-is
        if i < 2:
            refined += char
        # Positions 2-3: District number (should be digits) - apply corrections
        elif 2 <= i < 4:
            if char in corrections_numeric:
                refined += corrections_numeric[char]
            else:
                refined += char
        # Positions 4-7: Series letters (PA, PAZ, etc.) - keep letters, but fix obvious errors
        elif 4 <= i < 8:
            # Keep letters as-is (including Z, which is valid in series)
            # Only convert O and I if they're clearly numbers
            if char.isdigit():
                refined += char
            elif char == 'O' and (i >= 7 or (i < len(text) - 1 and text[i+1].isdigit())):
                # O followed by digit is likely 0
                refined += '0'
            elif char == 'I' and (i >= 7 or (i < len(text) - 1 and text[i+1].isdigit())):
                # I followed by digit is likely 1
                refined += '1'
            else:
                # Keep all other letters including Z, S, etc.
                refined += char
        # Positions 8+: Final number (should be all digits) - apply all corrections
        else:
            if char in corrections_numeric:
                refined += corrections_numeric[char]
            else:
                refined += char
    
    return refined

def clean_plate_text(text):
    """Clean and validate plate text with Indian license plate pattern matching"""
    if not text:
        return None
    
    # Remove non-alphanumeric characters
    cleaned = re.sub(r'[^A-Z0-9]', '', text.upper())
    
    # Apply pattern-based refinement
    refined = refine_plate_text(cleaned)
    
    if not refined:
        return None
    
    # Length check: Indian license plates are typically 9-10 characters
    # Allow 8-12 to handle OCR variations
    if not (9 <= len(refined) <= 12):
        logging.debug(f"Rejecting '{refined}' - invalid length ({len(refined)} chars)")
        return None
    
    # Must start with 2 letters (state code)
    if not (len(refined) >= 2 and refined[0].isalpha() and refined[1].isalpha()):
        logging.debug(f"Rejecting '{refined}' - doesn't start with 2 letters")
        return None
    
    # CRITICAL: Must end with at least 3 consecutive digits
    # Indian plates end with 4 digits (e.g., 2063, 1234)
    # This rejects plates like "HK16E7ST" which end with "ST"
    trailing_digits = 0
    for i in range(len(refined) - 1, -1, -1):
        if refined[i].isdigit():
            trailing_digits += 1
        else:
            break
    
    if trailing_digits < 3:
        logging.debug(f"Rejecting '{refined}' - doesn't end with at least 3 digits (has {trailing_digits})")
        return None
    
    # CRITICAL: License plates must contain BOTH letters AND numbers
    has_letter = any(c.isalpha() for c in refined)
    has_number = any(c.isdigit() for c in refined)
    
    if not (has_letter and has_number):
        logging.debug(f"Rejecting '{refined}' - missing letters or numbers")
        return None
    
    # Must have at least 3 digits total (Indian plates have 4+ digits)
    digit_count = sum(1 for c in refined if c.isdigit())
    if digit_count < 4:
        logging.debug(f"Rejecting '{refined}' - too few digits ({digit_count})")
        return None
    
    # Must have at least 3 letters (state code + series)
    letter_count = sum(1 for c in refined if c.isalpha())
    if letter_count < 3:
        logging.debug(f"Rejecting '{refined}' - too few letters ({letter_count})")
        return None
    
    # Reject if too many consecutive same characters (likely OCR error)
    # Allow 2 consecutive, reject 4+
    for i in range(len(refined) - 3):
        if refined[i] == refined[i+1] == refined[i+2] == refined[i+3]:
            logging.debug(f"Rejecting '{refined}' - has 4+ consecutive same characters")
            return None
    
    # Reject obvious patterns that indicate random text
    # Check if it's mostly random (too many unique character transitions)
    if len(refined) >= 10:
        # Count alternations between letters and numbers
        alternations = 0
        for i in range(len(refined) - 1):
            if (refined[i].isalpha() and refined[i+1].isdigit()) or \
               (refined[i].isdigit() and refined[i+1].isalpha()):
                alternations += 1
        
        # Indian plates have 2-3 alternations max (XX-00-XX-0000)
        # Random text has many more alternations
        if alternations > 4:
            logging.debug(f"Rejecting '{refined}' - too many alternations ({alternations})")
            return None
    
    return refined

def levenshtein_distance(s1, s2):
    """Calculate Levenshtein distance between two strings"""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost of insertions, deletions, or substitutions
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]

def is_similar_plate(plate1, plate2, threshold=2):
    """Check if two plates are similar using Levenshtein distance"""
    if not plate1 or not plate2:
        return False
    
    # Exact match
    if plate1 == plate2:
        return True
    
    # Fuzzy match with threshold (max 2 character differences)
    distance = levenshtein_distance(plate1, plate2)
    return distance <= threshold

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
        if os.path.exists("/app/ai_engine"):
            model_path = str(project_root / 'yolov8x.pt')
        else:
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
        # Try local model first, then Hub
        local_nozzle = os.path.join(os.path.dirname(__file__), "models", "nozzle_model.pt")
        if os.path.exists(local_nozzle):
            nozzle_model = YOLO(local_nozzle).to(device)
            logging.info(f"✓ Specialized Nozzle model loaded from local: {local_nozzle}")
            print(f"✓ Specialized Nozzle model loaded from local")
        else:
            # Fallback to a known stable model on Hub
            nozzle_model = YOLO("keremberke/fuel-nozzle-yolov8n").to(device)
            logging.info("✓ Specialized Nozzle model loaded from Hub")
            print("✓ Specialized Nozzle model loaded from Hub")
    except Exception as e:
        logging.warning(f"⚠ Failed to load specialized nozzle model: {e}")
        print(f"  Nozzle detection will use general object detector")
        nozzle_model = None

    # 4. OCR Reader (PaddleOCR with Tesseract Fallback)
    print("Initializing OCR Reader...")
    reader = None
    
    # Try PaddleOCR first for high accuracy plate reading
    try:
        from paddleocr import PaddleOCR
        logging.getLogger('ppocr').setLevel(logging.ERROR)
        reader = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)
        logging.info("✓ PaddleOCR initialized successfully as reader")
        print("✓ PaddleOCR initialized successfully")
    except Exception as paddle_err:
        logging.warning(f"⚠ PaddleOCR not available, falling back to Tesseract: {paddle_err}")
        print("⚠ PaddleOCR not available, trying Tesseract...")

    if reader is None:
        try:
            import pytesseract
            from PIL import Image
            
            # Configure Tesseract path (common Windows installation location)
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
            
            # Use a wrapper to mimic PaddleOCR's interface
            class TesseractPaddleWrapper:
                def __init__(self, pytesseract_module):
                    self.pytesseract = pytesseract_module
                def ocr(self, img, cls=True):
                    try:
                        text = self.pytesseract.image_to_string(img).strip()
                        if text:
                            return [[ [ [[0,0],[0,0],[0,0],[0,0]], (text, 0.90) ] ]]
                        return [[]]
                    except:
                        return [[]]
                def image_to_data(self, *args, **kwargs):
                    return self.pytesseract.image_to_data(*args, **kwargs)
            
            reader = TesseractPaddleWrapper(pytesseract)
            logging.info(f"✓ Tesseract OCR initialized as reader fallback (version: {test_version})")
            print(f"✓ Tesseract OCR initialized as reader fallback")
        except Exception as e:
            logging.warning(f"⚠ Failed to initialize Tesseract: {e}")
            print(f"⚠ Failed to initialize Tesseract: {e}")
            reader = None
    
    # Open video
    logging.info(f"Opening video: {video_path}")
    
    # Check if it's an RTSP or HTTP network stream
    is_network_stream = any(video_path.lower().startswith(p) for p in ['rtsp://', 'rtsps://', 'http://', 'https://'])
    
    if is_network_stream:
        # Network stream - use FFMPEG and buffer options for lower latency
        cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        logging.info(f"Opening network stream: {video_path}")
    else:
        # Regular video file
        cap = cv2.VideoCapture(video_path)
    
    if not cap.isOpened():
        error_msg = f"✗ Failed to open video: {video_path}"
        if is_network_stream:
            error_msg += "\n  Network stream connection failed. Check:"
            error_msg += "\n  - Stream is online and accessible"
            error_msg += "\n  - Stream URL is correct"
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
    # Tracking state
    track_records = {}  # track_id -> {best_plate, best_plate_conf, plate_img, ...}
    detected_plates = set()  # Track unique plates already detected in this video
    
    # ANPR Processor for multi-frame consensus
    anpr_processor = AnprProcessor()
    
    frame_count = 0
    start_time = time.time()
    
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
                
            # 4K PERFORMANCE & DISTANT OBJECT OPTIMIZATION:
            # For distant objects, we run detection on multiple scales.
            # 1. Standard Scale (for general tracking)
            tracking_frame = frame
            track_scale = 1.0
            if width > 1920:
                track_scale = 1280.0 / width
                tracking_frame = cv2.resize(frame, (1280, int(height * track_scale)))
                
            # Run Tracking on primary scale
            try:
                # tracker='botsort.yaml' or 'bytetrack.yaml'
                results = model.track(tracking_frame, persist=True, device=device, verbose=False)
            except Exception as e:
                logging.error(f"Tracking error at frame {frame_count}: {e}")
                continue
            
            # 2. Zoomed/High-Res Scale (for distant objects - every 10 frames)
            if frame_count % 10 == 0 and width >= 1920:
                # Run detection on a higher resolution for distant objects (no tracking, just detection)
                # to trigger new tracks or update existing ones
                try:
                    hires_results = model(frame, conf=0.15, verbose=False)
                    # We don't use these results for tracking immediately, 
                    # but they help YOLO "see" smaller objects in 4K
                except: pass
            
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
                            'best_object_conf': float(conf),  # Store initial YOLO object detection confidence
                            'ocr_count': 0,
                            'consensus_reached': False
                        }
                    
                    current_record = track_history[track_id]
                    
                    # Update best object confidence if current is higher
                    if float(conf) > current_record.get('best_object_conf', 0):
                        current_record['best_object_conf'] = float(conf)
                    
                    should_send = False
                    
                    # ANPR Logic with Performance Throttling
                    # 1. Only process vehicles
                    # 2. Only run OCR if consensus not reached or periodically
                    do_ocr = False
                    if detection_type in ['Car', 'Truck', 'Bike'] and reader:  # Removed plate_model requirement
                        # Throttle OCR: Run first frame always, then every 3rd
                        current_record['ocr_count'] += 1
                        if not current_record['consensus_reached'] or current_record['ocr_count'] % 10 == 0:
                            if current_record['ocr_count'] == 1 or current_record['ocr_count'] % 5 == 0:
                                do_ocr = True
                                logging.info(f"  [Track {track_id}] Triggering OCR (count: {current_record['ocr_count']})")
                    
                    # Initialize coordinates for original resolution
                    if track_scale != 1.0:
                        x1_orig = int(x1 / track_scale)
                        y1_orig = int(y1 / track_scale)
                        x2_orig = int(x2 / track_scale)
                        y2_orig = int(y2 / track_scale)
                    else:
                        x1_orig, y1_orig, x2_orig, y2_orig = x1, y1, x2, y2

                    object_image = frame[y1_orig:y2_orig, x1_orig:x2_orig].copy()
                        
                    if do_ocr:
                        if object_image.size > 0:
                            # Enhancement: Upscale small crops to improve detection
                            h, w = object_image.shape[:2]
                            scale_factor = 1.0
                            if w < 400: scale_factor = 2.0
                            elif w < 800: scale_factor = 1.5
                            
                            object_image_detector = cv2.resize(object_image, (int(w * scale_factor), int(h * scale_factor)), interpolation=cv2.INTER_CUBIC)

                            # Initialize detection variables for this object
                            best_text_to_use = None
                            avg_conf = conf # Use the vehicle confidence as the baseline
                            
                            # OCR-ONLY MODE: Process entire vehicle crop when no plate model available
                            if not plate_model:
                                logging.info(f"  [Track {track_id}] Using OCR-only mode on vehicle crop")
                                
                                # Multi-Pass OCR Enhancement on vehicle crop
                                variants = get_enhancement_variants(object_image_detector)
                                logging.info(f"  [Track {track_id}] Generated {len(variants)} enhancement variants")
                                
                                best_clean_text = None
                                best_ocr_conf = 0
                                
                                for i, variant in enumerate(variants):
                                    # Tesseract OCR processing
                                    try:
                                        from PIL import Image
                                        
                                        # Convert numpy array to PIL Image
                                        pil_image = Image.fromarray(cv2.cvtColor(variant, cv2.COLOR_BGR2RGB))
                                        
                                        # Try multiple Tesseract configurations for best results
                                        # PSM 7: Single text line (best for license plates)
                                        # PSM 8: Single word (fallback)
                                        # PSM 11: Sparse text (for difficult cases)
                                        configs = [
                                            r'--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                                            r'--psm 8 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789',
                                            r'--psm 11 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
                                        ]
                                        
                                        best_variant_text = None
                                        best_variant_conf = 0
                                        best_plate_bbox = None  # Store bounding box for cropping
                                        
                                        for config in configs:
                                            try:
                                                ocr_data = reader.image_to_data(pil_image, config=config, output_type='dict')
                                                
                                                # Extract text with confidence > 0 (very low threshold to catch everything)
                                                texts = []
                                                confidences = []
                                                bboxes = []  # Store bounding boxes
                                                for j, conf in enumerate(ocr_data['conf']):
                                                    try:
                                                        conf_val = int(conf)
                                                        if conf_val > 0:  # Very low threshold
                                                            text = ocr_data['text'][j]
                                                            if text.strip():
                                                                texts.append(text)
                                                                confidences.append(conf_val / 100.0)
                                                                # Store bounding box (x, y, w, h)
                                                                bboxes.append({
                                                                    'x': ocr_data['left'][j],
                                                                    'y': ocr_data['top'][j],
                                                                    'w': ocr_data['width'][j],
                                                                    'h': ocr_data['height'][j]
                                                                })
                                                    except (ValueError, TypeError):
                                                        continue
                                                
                                                if texts:
                                                    found_text = "".join(texts)
                                                    avg_conf = sum(confidences) / len(confidences) if confidences else 0
                                                    if avg_conf > best_variant_conf:
                                                        best_variant_conf = avg_conf
                                                        best_variant_text = found_text
                                                        # Calculate combined bounding box for all text
                                                        if bboxes:
                                                            min_x = min(b['x'] for b in bboxes)
                                                            min_y = min(b['y'] for b in bboxes)
                                                            max_x = max(b['x'] + b['w'] for b in bboxes)
                                                            max_y = max(b['y'] + b['h'] for b in bboxes)
                                                            best_plate_bbox = (min_x, min_y, max_x, max_y)
                                            except Exception:
                                                continue
                                        
                                        if not best_variant_text:
                                            logging.info(f"  [Track {track_id} Var {i}] No text detected")
                                            continue
                                            
                                        logging.info(f"  [Track {track_id} Var {i}] Raw OCR: '{best_variant_text}'")
                                        clean_text = clean_plate_text(best_variant_text)
                                        
                                        if clean_text:
                                            logging.info(f"  [Track {track_id} Var {i}] Clean OCR: '{clean_text}' (conf: {best_variant_conf:.2f})")
                                            if best_variant_conf > best_ocr_conf:
                                                best_ocr_conf = best_variant_conf
                                                best_clean_text = clean_text
                                        else:
                                            logging.info(f"  [Track {track_id} Var {i}] Text filtered out: '{best_variant_text}'")
                                    except Exception as ocr_err:
                                        logging.error(f"  [Track {track_id} Var {i}] OCR error: {ocr_err}")
                                        continue
                                
                                if best_clean_text:
                                    avg_conf = (conf + best_ocr_conf) / 2
                                    consensus_text = anpr_processor.add_prediction(track_id, best_clean_text, avg_conf)
                                    best_text_to_use = consensus_text or best_clean_text
                                    
                                    if consensus_text and avg_conf > 0.6:
                                        current_record['consensus_reached'] = True
                                    
                                    # Crop plate region if we have bounding box
                                    plate_image = object_image  # Default to vehicle crop
                                    if best_plate_bbox:
                                        try:
                                            x1, y1, x2, y2 = best_plate_bbox
                                            # Ensure coordinates are in correct order
                                            x1, x2 = min(x1, x2), max(x1, x2)
                                            y1, y2 = min(y1, y2), max(y1, y2)
                                            
                                            # Add padding around the plate (10% on each side)
                                            h, w = object_image.shape[:2]
                                            pad_x = int((x2 - x1) * 0.1)
                                            pad_y = int((y2 - y1) * 0.1)
                                            x1 = max(0, x1 - pad_x)
                                            y1 = max(0, y1 - pad_y)
                                            x2 = min(w, x2 + pad_x)
                                            y2 = min(h, y2 + pad_y)
                                            
                                            # Validate crop dimensions
                                            if x2 > x1 and y2 > y1:
                                                # Crop the plate region
                                                plate_image = object_image[y1:y2, x1:x2]
                                                logging.info(f"  [Track {track_id}] Cropped plate region: {x1},{y1} to {x2},{y2}")
                                            else:
                                                logging.warning(f"  [Track {track_id}] Invalid crop dimensions, using full vehicle")
                                        except Exception as crop_err:
                                            logging.warning(f"  [Track {track_id}] Failed to crop plate: {crop_err}")
                                            plate_image = object_image  # Fall back to full vehicle
                                    
                                    # Update best plate info
                                    current_record['best_plate'] = best_text_to_use
                                    current_record['best_plate_conf'] = avg_conf
                                    current_record['plate_img'] = plate_image  # Use cropped plate image
                                    
                                    # Check if this plate was already detected (exact or similar)
                                    is_duplicate = False
                                    for existing_plate in detected_plates:
                                        if is_similar_plate(best_text_to_use, existing_plate, threshold=2):
                                            logging.info(f"  [Track {track_id}] ⚠ Plate '{best_text_to_use}' is similar to '{existing_plate}', skipping duplicate")
                                            is_duplicate = True
                                            break
                                    
                                    if is_duplicate:
                                        should_send = False  # Don't send duplicate
                                    else:
                                        detected_plates.add(best_text_to_use)  # Mark as detected
                                        should_send = True
                                        logging.info(f"  [Track {track_id}] ✓ Plate detected: {best_text_to_use} (conf: {avg_conf:.2f})")
                                else:
                                    logging.info(f"  [Track {track_id}] OCR Failed on all {len(variants)} variants")
                            
                            else:
                                # PLATE MODEL MODE: Use YOLO to find plate, then OCR
                                plate_results = plate_model(object_image_detector, conf=0.20, verbose=False)
                                
                                if not plate_results or len(plate_results[0].boxes) == 0:
                                    logging.debug(f"  [Track {track_id}] No plate found by YOLO (conf > 0.20)")

                                for p_res in plate_results:
                                    if p_res.boxes is None: continue
                                    for p_box in p_res.boxes:
                                        px1, py1, px2, py2 = p_box.xyxy[0].cpu().numpy().astype(int)
                                        p_conf_val = float(p_box.conf[0])
                                        logging.debug(f"  [Track {track_id}] Plate candidate found (YOLO conf: {p_conf_val:.2f})")
                                    
                                    plate_crop = object_image_detector[py1:py2, px1:px2].copy()
                                    if plate_crop.size > 0:
                                        # Multi-Pass OCR Enhancement
                                        variants = get_enhancement_variants(plate_crop)
                                        
                                        best_clean_text = None
                                        best_ocr_conf = 0
                                        
                                        for i, variant in enumerate(variants):
                                            # PaddleOCR returns: [[[box], (text, confidence)]]
                                            try:
                                                ocr_results = reader.ocr(variant, cls=True)
                                                if not ocr_results or not ocr_results[0]:
                                                    continue
                                                
                                                # Extract text and confidence from PaddleOCR format
                                                texts = []
                                                confidences = []
                                                for line in ocr_results[0]:
                                                    if line and len(line) >= 2:
                                                        text, conf = line[1]
                                                        if conf > 0.10:  # Filter low confidence
                                                            texts.append(text)
                                                            confidences.append(conf)
                                                
                                                if not texts:
                                                    continue
                                                    
                                                found_text = "".join(texts)
                                                logging.debug(f"  [Track {track_id} Var {i}] Raw OCR: '{found_text}'")
                                                clean_text = clean_plate_text(found_text)
                                                
                                                if clean_text:
                                                    # Calculate average confidence
                                                    v_conf = sum(confidences) / len(confidences)
                                                    logging.debug(f"  [Track {track_id} Var {i}] Clean OCR: '{clean_text}' (conf: {v_conf:.2f})")
                                                    if v_conf > best_ocr_conf:
                                                        best_ocr_conf = v_conf
                                                        best_clean_text = clean_text
                                            except Exception as ocr_err:
                                                logging.debug(f"  [Track {track_id} Var {i}] OCR error: {ocr_err}")
                                                continue
                                        
                                        if best_clean_text == None:
                                            logging.debug(f"  [Track {track_id}] OCR Failed on all {len(variants)} variants")
                                        
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
                                        
                                        # 1. Aspect Ratio Check (Plates are rectangular or square-ish)
                                        pw, ph = (px2 - px1), (py2 - py1)
                                        aspect_ratio = pw / float(ph) if ph > 0 else 0
                                        
                                        # 2. Area ratio check (plate area / vehicle area)
                                        # Use actual dimensions of the crop being processed by the detector
                                        h_det, w_det = object_image_detector.shape[:2]
                                        vehicle_area_det = h_det * w_det
                                        plate_area = pw * ph
                                        area_ratio = plate_area / vehicle_area_det
                                        
                                        # RELAXED Filtering for better recall:
                                        # - Aspect ratio: 0.8 to 8.0 (handles various plate orientations)
                                        # - Area ratio: 0.1% to 40% of vehicle crop
                                        if aspect_ratio < 0.8 or aspect_ratio > 8.0:
                                            logging.info(f"  [Track {track_id}] Plate filtered (bad aspect: {aspect_ratio:.2f})")
                                            is_false_positive = True
                                        elif area_ratio < 0.001 or area_ratio > 0.40:
                                            logging.info(f"  [Track {track_id}] Plate filtered (bad size ratio: {area_ratio:.3f})")
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
                        # Use original resolution coordinates for backend
                        if True: # Send all tracked objects immediately (Humans, Cars, Trucks, etc.)
                            # Use original resolution coordinates for backend
                            bbox_orig = [x1_orig, y1_orig, x2_orig, y2_orig]
                            geo_marker_id = check_in_geo_fence(bbox_orig, geo_fences)
                            
                            object_image_full = frame[y1_orig:y2_orig, x1_orig:x2_orig].copy()
                            
                            # RESOLUTION ENHANCEMENT: Upscale small crops for better web visibility
                            if object_image_full.size > 0:
                                h_i, w_i = object_image_full.shape[:2]
                                if w_i < 320 or h_i < 320:
                                    scale = max(1.0, 320 / min(w_i, h_i))
                                    if scale > 1.0:
                                        object_image_full = cv2.resize(object_image_full, (int(w_i * scale), int(h_i * scale)), interpolation=cv2.INTER_CUBIC)
                            
                            # Confidence score represents YOLO object detection confidence
                            # This is how confident the AI is about detecting the object type (Car, Truck, Human, etc.)
                            # Use the best confidence seen across all frames for this track
                            object_confidence = current_record.get('best_object_conf', float(conf))
                            
                            # Ensure confidence is in valid range (0.0 to 1.0)
                            object_confidence = max(0.0, min(1.0, object_confidence))
                            
                            # Log confidence for debugging
                            plate_conf = current_record.get('best_plate_conf', 'N/A')
                            logging.info(f"[Track {track_id}] Object confidence: current={conf:.3f}, best={object_confidence:.3f}, Plate: {plate_conf}")
                            
                            detection_data = {
                                "detection_type": detection_type,
                                "camera_id": camera_id,
                                "track_id": track_id,
                                "confidence_score": object_confidence,
                                "object_image": object_image_full,
                                "numberplate_text": current_record['best_plate'],
                                "numberplate_image": current_record.get('plate_img'),
                                "geo_marker_id": geo_marker_id
                            }
                            logging.debug(f"[Track {track_id}] Sending confidence: vehicle={conf:.3f}, best={object_confidence:.3f}")
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

            # Specialized Nozzle Detection
            if nozzle_model:
                try:
                    # Run on original frame for better precision if object is distant
                    # Throttled to every 4th frame for performance
                    if frame_count % 4 == 0:
                        n_results = nozzle_model(frame, conf=0.30, verbose=False) 
                        for n_res in n_results:
                            if n_res.boxes is None: continue
                            n_boxes = n_res.boxes.xyxy.cpu().numpy().astype(int)
                            n_confs = n_res.boxes.conf.cpu().numpy().astype(float)
                            
                            for n_box, n_conf in zip(n_boxes, n_confs):
                                x1_n, y1_n, x2_n, y2_n = n_box
                                
                                # Safety crop
                                y1_n, y2_n = max(0, y1_n), min(height, y2_n)
                                x1_n, x2_n = max(0, x1_n), min(width, x2_n)
                                
                                n_crop = frame[y1_n:y2_n, x1_n:x2_n].copy()
                                if n_crop.size == 0: continue
                                
                                # RESOLUTION ENHANCEMENT for Nozzle
                                hn, wn = n_crop.shape[:2]
                                if wn < 320 or hn < 320:
                                    n_scale = max(1.0, 320 / min(wn, hn))
                                    n_crop = cv2.resize(n_crop, (int(wn * n_scale), int(hn * n_scale)), interpolation=cv2.INTER_CUBIC)

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
        # cv2.destroyAllWindows() not needed for headless processing
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

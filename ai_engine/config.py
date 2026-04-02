"""
ANPR Configuration Settings
Centralized configuration for high-precision number plate detection
"""

# Detection Confidence Thresholds
VEHICLE_DETECTION_CONF = 0.25  # YOLOv8 vehicle detection confidence
PLATE_DETECTION_CONF = 0.15    # License plate YOLO confidence (lowered for distant plates)
OCR_MIN_CONFIDENCE = 0.10      # Minimum OCR character confidence

# Filtering Thresholds (Relaxed for better recall)
PLATE_ASPECT_RATIO_MIN = 0.8   # Minimum width/height ratio (was 1.0)
PLATE_ASPECT_RATIO_MAX = 8.0   # Maximum width/height ratio (was 7.0)
PLATE_AREA_RATIO_MIN = 0.001   # Minimum plate area / vehicle area (was 0.003)
PLATE_AREA_RATIO_MAX = 0.40    # Maximum plate area / vehicle area (was 0.30)

# Multi-Scale Detection Settings
ENABLE_MULTI_SCALE = True
SCALE_FACTORS = [1.0, 1.5, 2.0]  # Process at original, 1.5x, and 2x resolution
MIN_PLATE_WIDTH = 40             # Minimum plate width in pixels before upscaling

# Image Enhancement Settings
UPSCALE_FACTOR = 2.0            # Default upscaling for small plates
CLAHE_CLIP_LIMIT = 2.0          # Contrast enhancement limit
CLAHE_TILE_SIZE = (8, 8)        # CLAHE tile grid size
DENOISE_STRENGTH = 10           # Denoising filter strength

# ANPR Processor Settings
ANPR_BUFFER_SIZE = 20           # Temporal buffer for consensus (was 12)
ANPR_MIN_VOTES = 3              # Minimum votes for consensus (was 4)
MIN_PLATE_LENGTH = 4            # Minimum valid plate text length

# PaddleOCR Settings
PADDLEOCR_USE_GPU = True        # Auto-detect GPU
PADDLEOCR_LANG = 'en'           # Language
PADDLEOCR_USE_ANGLE_CLS = True  # Enable angle classification for rotated plates
PADDLEOCR_DET_DB_THRESH = 0.3   # Detection threshold
PADDLEOCR_DET_DB_BOX_THRESH = 0.5  # Box threshold

# Performance Settings
PROCESS_INTERVAL = 2            # Process every Nth frame
OCR_THROTTLE_INTERVAL = 5       # Run OCR every Nth detection for same track
DETECTION_SEND_INTERVAL = 2.0   # Seconds between sending same track to backend

# Model Paths
YOLO_MAIN_MODEL = "yolov8x.pt"
YOLO_PLATE_MODEL = "ai_engine/models/license_plate.pt"

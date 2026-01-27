import cv2
import numpy as np

def enhance_plate_v1(image):
    """Strategy 1: Grayscale + CLAHE + Soft Sharpening"""
    if image is None or image.size == 0: return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    kernel = np.array([[-1, -1, -1], [-1, 7, -1], [-1, -1, -1]])
    return cv2.filter2D(enhanced, -1, kernel)

def enhance_plate_v2(image):
    """Strategy 2: Grayscale + Denoise + Strong Sharpening"""
    if image is None or image.size == 0: return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    kernel = np.array([[-1, -1, -1], [-1, 9, -1], [-1, -1, -1]])
    return cv2.filter2D(denoised, -1, kernel)

def enhance_plate_v3(image):
    """Strategy 3: Adaptive Thresholding (Binarization)"""
    if image is None or image.size == 0: return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    return cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

def enhance_plate_v4(image):
    """Strategy 4: Bilateral Filter + Morphological Opening (Ultra-Clean)"""
    if image is None or image.size == 0: return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    filtered = cv2.bilateralFilter(gray, 9, 75, 75)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    return cv2.morphologyEx(filtered, cv2.MORPH_OPEN, kernel)

def get_enhancement_variants(image):
    """Return a list of enhanced image variants to try for OCR"""
    if image is None or image.size == 0: return []
    
    # Always include a scaled original version
    scaled_orig = upscale_image(image, 2)
    gray_orig = cv2.cvtColor(scaled_orig, cv2.COLOR_BGR2GRAY) if len(scaled_orig.shape) == 3 else scaled_orig
    
    variants = [
        gray_orig,
        enhance_plate_v1(gray_orig),
        enhance_plate_v2(gray_orig),
        enhance_plate_v3(gray_orig),
        enhance_plate_v4(gray_orig)
    ]
    return [v for v in variants if v is not None]

def upscale_image(image, scale_factor=2):
    """Upscale image using cubic interpolation for better detail retention"""
    if image is None or image.size == 0:
        return image
    h, w = image.shape[:2]
    return cv2.resize(image, (int(w * scale_factor), int(h * scale_factor)), interpolation=cv2.INTER_CUBIC)

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

def enhance_plate_v5(image):
    """Strategy 5: Bilateral Filter + Unsharp Masking (Best for blurry plates)"""
    if image is None or image.size == 0: return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    # Bilateral filter preserves edges while reducing noise
    bilateral = cv2.bilateralFilter(gray, 9, 75, 75)
    # Unsharp masking for sharpening
    gaussian = cv2.GaussianBlur(bilateral, (0, 0), 2.0)
    unsharp = cv2.addWeighted(bilateral, 1.5, gaussian, -0.5, 0)
    return unsharp

def enhance_plate_v6(image):
    """Strategy 6: Motion Deblur + High Contrast (For moving vehicles)"""
    if image is None or image.size == 0: return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    # Wiener-like deconvolution approximation
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    sharpened = cv2.filter2D(gray, -1, kernel)
    # High contrast
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    return clahe.apply(sharpened)

def enhance_plate_v7(image):
    """Strategy 7: Super-Resolution Upscaling (For distant/small plates)"""
    if image is None or image.size == 0: return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    # 4x upscaling with edge-preserving interpolation
    h, w = gray.shape[:2]
    upscaled = cv2.resize(gray, (w * 4, h * 4), interpolation=cv2.INTER_CUBIC)
    # Apply CLAHE for better contrast
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(upscaled)
    return enhanced

def get_enhancement_variants(image):
    """Return a list of enhanced image variants to try for OCR"""
    if image is None or image.size == 0: return []
    
    # Always include a scaled original version
    scaled_orig = upscale_image(image, 2)
    gray_orig = cv2.cvtColor(scaled_orig, cv2.COLOR_BGR2GRAY) if len(scaled_orig.shape) == 3 else scaled_orig
    
    # Return 7 variants for comprehensive OCR attempts
    variants = [
        gray_orig,
        enhance_plate_v1(gray_orig),
        enhance_plate_v2(gray_orig),
        enhance_plate_v3(gray_orig),
        enhance_plate_v4(gray_orig),
        enhance_plate_v5(gray_orig),  # NEW: Best for blur
        enhance_plate_v6(gray_orig),  # NEW: Best for motion
        enhance_plate_v7(image)       # NEW: Best for distant (uses original color)
    ]
    return [v for v in variants if v is not None]

def upscale_image(image, scale_factor=2):
    """Upscale image using cubic interpolation for better detail retention"""
    if image is None or image.size == 0:
        return image
    h, w = image.shape[:2]
    return cv2.resize(image, (int(w * scale_factor), int(h * scale_factor)), interpolation=cv2.INTER_CUBIC)

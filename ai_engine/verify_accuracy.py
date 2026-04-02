import cv2
import numpy as np
import easyocr
import sys
import os
from ai_engine.image_utils import enhance_plate_image, upscale_image

def verify_enhancements(image_path):
    if not os.path.exists(image_path):
        print(f"File not found: {image_path}")
        return

    # Load image
    img = cv2.imread(image_path)
    if img is None:
        print("Failed to load image")
        return

    # Initialize EasyOCR
    print("Initializing OCR...")
    reader = easyocr.Reader(['en'], gpu=False) # CPU for small tests

    # 1. OCR on Original
    print("\n--- Original Image OCR ---")
    results_orig = reader.readtext(img)
    text_orig = " ".join([t for _, t, c in results_orig if c > 0.1])
    print(f"Detected Text: {text_orig}")

    # 2. OCR on Enhanced
    print("\n--- Enhanced Image OCR ---")
    enhanced = enhance_plate_image(img)
    # Upscale if needed
    enhanced = upscale_image(enhanced, 2)
    
    results_enh = reader.readtext(enhanced)
    text_enh = " ".join([t for _, t, c in results_enh if c > 0.1])
    print(f"Detected Text: {text_enh}")
    
    # Save results for manual inspection
    cv2.imwrite("verification_original.jpg", img)
    cv2.imwrite("verification_enhanced.jpg", enhanced)
    print("\nSaved verification_original.jpg and verification_enhanced.jpg")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python ai_engine/verify_accuracy.py <image_path>")
    else:
        verify_enhancements(sys.argv[1])

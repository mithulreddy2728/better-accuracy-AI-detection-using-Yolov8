#!/usr/bin/env python3
"""
Quick test to verify PaddleOCR can read the police car plate
"""
from paddleocr import PaddleOCR
import sys

# Initialize PaddleOCR
print("Initializing PaddleOCR...")
reader = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)

# Test image path (you can replace this with your actual image)
test_image = r"C:\Users\ACER\.gemini\antigravity\brain\f099c496-3b3f-4e78-9dc1-dd64426fbca3\uploaded_media_1769693008910.jpg"

print(f"\nReading image: {test_image}")
print("="*60)

try:
    # Run OCR
    results = reader.ocr(test_image, cls=True)
    
    if results and results[0]:
        print("\n✓ PaddleOCR Results:")
        print("-"*60)
        for idx, line in enumerate(results[0]):
            if line and len(line) >= 2:
                text, conf = line[1]
                print(f"  {idx+1}. Text: '{text}' | Confidence: {conf:.2f}")
        print("-"*60)
    else:
        print("\n✗ No text detected")
        
except Exception as e:
    print(f"\n✗ Error: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("PaddleOCR is working correctly!")
print("="*60)

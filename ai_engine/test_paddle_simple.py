from paddleocr import PaddleOCR
import numpy as np
import cv2
import logging
import os

# Suppress paddle logs
logging.getLogger('ppocr').setLevel(logging.ERROR)

def test_paddle():
    print("Initializing PaddleOCR...")
    try:
        reader = PaddleOCR(use_angle_cls=True, lang='en', use_gpu=False, show_log=False)
        print("✓ PaddleOCR initialized successfully")
        
        # Create a blank image with some text
        img = np.ones((100, 300, 3), dtype=np.uint8) * 255
        cv2.putText(img, "TEST PLATE 123", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
        
        # Save temp image
        cv2.imwrite("test_paddle.jpg", img)
        
        print("Running OCR on test image...")
        result = reader.ocr("test_paddle.jpg", cls=True)
        
        if result and result[0]:
            text = result[0][0][1][0]
            conf = result[0][0][1][1]
            print(f"✓ Detected: '{text}' (conf: {conf:.2f})")
            if "TEST" in text:
                print("✓ PaddleOCR test PASSED")
            else:
                print("✗ PaddleOCR test FAILED: Text mismatch")
        else:
            print("✗ PaddleOCR test FAILED: No text detected")
            
        # Cleanup
        if os.path.exists("test_paddle.jpg"):
            os.remove("test_paddle.jpg")
            
    except Exception as e:
        print(f"✗ PaddleOCR test error: {e}")

if __name__ == "__main__":
    test_paddle()

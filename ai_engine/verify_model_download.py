import requests
from pathlib import Path

def download_and_verify():
    # This is a confirmed YOLOv8 plate model from a reputable source
    url = "https://github.com/computervisioneng/automatic-number-plate-recognition-python-yolov8/raw/main/models/license_plate_detector.pt"
    dest = Path("ai_engine/models/license_plate.pt")
    
    print(f"Downloading model from: {url}")
    try:
        r = requests.get(url, allow_redirects=True, timeout=30)
        r.raise_for_status()
        
        # Check if the content is likely a model (binary) or an error page (HTML)
        content_start = r.content[:50]
        if b"<!DOCTYPE html>" in content_start or b"<html>" in content_start.lower():
            print("ERROR: Downloaded an HTML page instead of the model file. Possible URL change or block.")
            return False
            
        with open(dest, "wb") as f:
            f.write(r.content)
            
        print(f"SUCCESS: Model saved as {dest}")
        print(f"File size: {dest.stat().st_size} bytes")
        print(f"First 4 bytes (HEX): {r.content[:4].hex()}")
        
        # Standard PyTorch files usually start with PK (504b) for zip or other binary headers
        return True
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return False

if __name__ == "__main__":
    download_and_verify()

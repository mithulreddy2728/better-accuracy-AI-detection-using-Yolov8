#!/usr/bin/env python3
"""
Download a working license plate detection model from alternative sources
"""
import os
import requests
from pathlib import Path

def download_model():
    """Download license plate model from multiple sources"""
    
    models_dir = Path(__file__).parent / "models"
    models_dir.mkdir(exist_ok=True)
    
    model_path = models_dir / "license_plate.pt"
    
    # Alternative sources for license plate models
    sources = [
        {
            "name": "Ultralytics Hub - License Plate v8",
            "url": "https://github.com/niconielsen32/LicensePlateDetector/raw/main/license_plate_detector.pt",
            "size": "6MB"
        },
        {
            "name": "RoboFlow - License Plate YOLOv8",
            "url": "https://github.com/MuhammadMoinFaisal/Automatic_Number_Plate_Detection_Recognition_YOLOv8/raw/main/license_plate_detector.pt",
            "size": "6MB"
        }
    ]
    
    for source in sources:
        print(f"\n{'='*60}")
        print(f"Trying: {source['name']}")
        print(f"Expected size: {source['size']}")
        print(f"{'='*60}\n")
        
        try:
            print(f"Downloading from {source['url']}...")
            response = requests.get(source['url'], stream=True, timeout=30)
            
            if response.status_code == 200:
                total_size = int(response.headers.get('content-length', 0))
                
                with open(model_path, 'wb') as f:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress = (downloaded / total_size) * 100
                                print(f"\rProgress: {progress:.1f}%", end='', flush=True)
                
                print(f"\n✓ Downloaded successfully!")
                
                # Verify file size
                file_size = os.path.getsize(model_path)
                print(f"File size: {file_size / (1024*1024):.2f} MB")
                
                if file_size > 1000000:  # At least 1MB
                    print(f"\n✓ Model ready at: {model_path}")
                    return True
                else:
                    print(f"✗ File too small, trying next source...")
                    os.remove(model_path)
                    
        except Exception as e:
            print(f"✗ Failed: {e}")
            if model_path.exists():
                os.remove(model_path)
            continue
    
    print("\n" + "="*60)
    print("✗ All download attempts failed")
    print("="*60)
    print("\nManual download instructions:")
    print("1. Visit: https://github.com/niconielsen32/LicensePlateDetector")
    print("2. Download 'license_plate_detector.pt'")
    print(f"3. Save to: {model_path}")
    return False

if __name__ == "__main__":
    download_model()

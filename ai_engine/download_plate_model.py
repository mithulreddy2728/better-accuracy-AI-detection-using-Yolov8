#!/usr/bin/env python3
"""
Download a pre-trained YOLOv8 license plate detection model.
This script attempts to download from multiple sources.
"""

import os
import sys
import requests
from pathlib import Path

def download_file(url, destination):
    """Download a file from URL to destination"""
    print(f"Downloading from {url}...")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        
        with open(destination, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"\rProgress: {progress:.1f}%", end='', flush=True)
        
        print(f"\n✓ Downloaded successfully to {destination}")
        return True
    except Exception as e:
        print(f"\n✗ Failed to download: {e}")
        return False

def main():
    # Set up paths
    script_dir = Path(__file__).parent
    models_dir = script_dir / "models"
    models_dir.mkdir(exist_ok=True)
    
    destination = models_dir / "license_plate.pt"
    
    if destination.exists():
        print(f"Model already exists at {destination}")
        overwrite = input("Overwrite? (y/n): ").lower()
        if overwrite != 'y':
            print("Skipping download.")
            return
    
    # Try multiple sources
    sources = [
        # High Accuracy Hugging Face Model
        "https://huggingface.co/AZIIIIIIIIZ/License-plate-detection/resolve/main/best.pt?download=true",
        # GitHub raw file from a known ANPR project
        "https://github.com/computervisioneng/automatic-number-plate-recognition-python-yolov8/raw/main/models/license_plate_detector.pt",
        # Alternative GitHub source
        "https://github.com/SiddharthUchil/ANPR-YOLOv8/raw/main/best.pt",
    ]
    
    print("Attempting to download YOLOv8 license plate detection model...")
    print("=" * 60)
    
    for i, url in enumerate(sources, 1):
        print(f"\nAttempt {i}/{len(sources)}")
        if download_file(url, destination):
            print(f"\n✓ Model ready at: {destination}")
            return
    
    print("\n" + "=" * 60)
    print("✗ All automatic download attempts failed.")
    print("\nManual download instructions:")
    print("1. Visit: https://www.kaggle.com/datasets/andrewmvd/car-plate-detection")
    print("   OR: https://github.com/computervisioneng/automatic-number-plate-recognition-python-yolov8")
    print("2. Download the 'best.pt' or 'license_plate_detector.pt' file")
    print(f"3. Save it as: {destination}")
    print("\nAlternatively, the system will work without a specialized plate model,")
    print("but accuracy will be lower (OCR-only mode).")

if __name__ == "__main__":
    main()

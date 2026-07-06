import requests
import os
from pathlib import Path

def download_model():
    url = "https://huggingface.co/AZIIIIIIIIZ/License-plate-detection/resolve/main/best.pt?download=true"
    dest = Path("ai_engine/models/license_plate.pt")
    
    # Ensure directory exists
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading high-accuracy model from: {url}")
    print(f"Saving to: {dest.absolute()}")
    
    try:
        response = requests.get(url, allow_redirects=True, stream=True, timeout=60)
        response.raise_for_status()
        
        with open(dest, 'wb') as f:
            downloaded = 0
            for chunk in response.iter_content(chunk_size=1024*1024): # 1MB chunks
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    print(f"\rDownloaded: {downloaded / (1024*1024):.2f} MB", end="")
        
        print("\n✓ Download complete!")
        
        # Basic integrity check (should be > 5MB)
        size = dest.stat().st_size
        if size < 5 * 1024 * 1024:
            print(f"⚠ Warning: File size is unusually small ({size} bytes). It might be a pointer file.")
        else:
            print(f"✓ File size verified: {size / (1024*1024):.2f} MB")
            
    except Exception as e:
        print(f"\n✗ Error: {e}")

if __name__ == "__main__":
    download_model()

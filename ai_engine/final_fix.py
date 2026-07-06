import requests
from pathlib import Path

def final_fix():
    # Use the keremberke model as it's very reliable
    url = "https://huggingface.co/keremberke/yolov8n-license-plate-detection/resolve/main/best.pt?download=true"
    dest = Path("ai_engine/models/license_plate.pt")
    dest.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Final attempt: Downloading from {url}")
    
    try:
        r = requests.get(url, allow_redirects=True, stream=True, timeout=60)
        r.raise_for_status()
        
        with open(dest, 'wb') as f:
            for chunk in r.iter_content(chunk_size=1024*1024):
                if chunk:
                    f.write(chunk)
        
        print(f"Download complete: {dest.stat().st_size / (1024*1024):.2f} MB")
        
        # Verify header
        with open(dest, 'rb') as f:
            header = f.read(4)
            print(f"File header: {header}")
            if header == b'PK\x03\x04':
                print("✓ Verified: Valid ZIP/PyTorch signature found.")
            else:
                print("⚠ Warning: Invalid signature. This might not be a YOLOv8 weight file.")
                
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    final_fix()

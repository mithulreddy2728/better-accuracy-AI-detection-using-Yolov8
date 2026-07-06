#!/usr/bin/env python3
"""
💻 Host Webcam Streamer for Docker AI Detection Engine
This script streams your laptop's built-in webcam over HTTP so that
the Dockerized backend can access it.

Prerequisites:
    pip install opencv-python

Usage:
    python ai_engine/share_webcam.py
"""

import sys
import time
import socket
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn

# Try importing OpenCV
try:
    import cv2
except ImportError:
    print("❌ OpenCV not found. Please install it by running:")
    print("   pip install opencv-python")
    sys.exit(1)

# Global video capture object
camera = None

def get_ip_address():
    """Get local IP address of this machine"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

class CamHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global camera
        if self.path == '/' or self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            
            print(f"🟢 Client connected: {self.client_address[0]}")
            try:
                while True:
                    if camera is None or not camera.isOpened():
                        time.sleep(0.1)
                        continue
                        
                    success, frame = camera.read()
                    if not success:
                        time.sleep(0.01)
                        continue
                    
                    # Encode frame as JPEG
                    ret, jpeg = cv2.imencode('.jpg', frame)
                    if not ret:
                        continue
                        
                    # Send MJPEG boundaries and frame content-type headers directly to wfile
                    self.wfile.write(b'--frame\r\n')
                    self.wfile.write(b'Content-Type: image/jpeg\r\n')
                    self.wfile.write(f'Content-Length: {len(jpeg)}\r\n\r\n'.encode('utf-8'))
                    self.wfile.write(jpeg.tobytes())
                    self.wfile.write(b'\r\n')
                    
                    # Limit stream to ~30 frames per second
                    time.sleep(0.03)
            except (ConnectionResetError, BrokenPipeError):
                print(f"🔴 Client disconnected: {self.client_address[0]}")
            except Exception as e:
                print(f"⚠ Error in stream handler: {e}")
        else:
            self.send_response(404)
            self.end_headers()

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""
    allow_reuse_address = True

def main():
    global camera
    PORT = 8085
    local_ip = get_ip_address()

    print("=" * 60)
    print("🎥 Starting Host Webcam Streamer...")
    print("=" * 60)

    # Initialize camera (0 is usually the default built-in webcam)
    print("Initializing webcam (Device 0)...")
    camera = cv2.VideoCapture(0)
    
    if not camera.isOpened():
        print("❌ Error: Could not access the built-in webcam (Device 0).")
        print("   Make sure no other app (Zoom, Teams, etc.) is using the camera.")
        sys.exit(1)
        
    print("✓ Webcam initialized successfully.")

    server = ThreadedHTTPServer(('0.0.0.0', PORT), CamHandler)
    print("\n🚀 Stream Server is running globally!")
    print(f"   • Local URL (Host): http://localhost:{PORT}/stream")
    print(f"   • Docker URL (use this in the app): http://host.docker.internal:{PORT}/stream")
    print(f"   • Network URL (other devices): http://{local_ip}:{PORT}/stream")
    print("\n📋 How to add it to the dashboard:")
    print("   1. Log in to the web interface (http://localhost)")
    print("   2. Navigate to 'Cameras'")
    print("   3. Click 'Add Camera'")
    print("   4. Set 'Type' to 'URL'")
    print(f"   5. Set 'Source' to: http://host.docker.internal:{PORT}/stream")
    print("   6. Click Save and start monitoring!")
    print("=" * 60)
    print("Press Ctrl+C to stop the stream server.")
    print("=" * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping stream server...")
    finally:
        if camera is not None:
            camera.release()
        server.server_close()
        print("✓ Stopped successfully.")

if __name__ == '__main__':
    main()

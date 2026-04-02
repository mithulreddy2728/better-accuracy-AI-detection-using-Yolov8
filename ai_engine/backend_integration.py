import requests
import time
from datetime import datetime, timedelta
import threading
import base64
import cv2
import numpy as np

class BackendIntegration:
    def __init__(self, api_base_url="http://localhost:8000"):
        self.api_base_url = api_base_url
        self.last_detections = {}  # camera_id -> {detection_key: timestamp}
        self.duplicate_window = 0.5  # Reduced window for high-frequency tracking updates
        self.geo_fences = {}  # camera_id -> list of geo-fences
        self.auth_token = None
        self.login()

    def login(self):
        """Login to get auth token"""
        try:
            response = requests.post(f"{self.api_base_url}/login", json={
                "username": "admin",
                "password": "admin"
            })
            if response.status_code == 200:
                self.auth_token = response.json()['access_token']
                print("✓ AI Engine authenticated successfully")
                return True
            else:
                print(f"✗ Failed to authenticate: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Authentication error: {e}")
            return False

    def encode_image_base64(self, image):
        """Encode OpenCV image to base64 string"""
        if image is None or image.size == 0:
            return None
        try:
            # Encode image to JPEG
            _, buffer = cv2.imencode('.jpg', image)
            # Convert to base64
            image_base64 = base64.b64encode(buffer).decode('utf-8')
            return f"data:image/jpeg;base64,{image_base64}"
        except Exception as e:
            print(f"Error encoding image: {e}")
            return None

    def is_duplicate(self, camera_id, detection_type, timestamp, track_id=None):
        """Check if detection was sent recently (backend also checks)"""
        if track_id is not None:
            key = f"{camera_id}_{detection_type}_{track_id}"
        else:
            key = f"{camera_id}_{detection_type}"
            
        if key not in self.last_detections:
            return False # Always allow first detection for a new track/key
            
        last_time = self.last_detections[key]
        return (datetime.utcnow() - last_time).total_seconds() < self.duplicate_window

    def send_detection(self, detection_data):
        """
        Send detection data to backend
        detection_data should contain:
        - detection_type: "Fuel Nozzle", "Car", "Bike", "Human", "Truck"
        - camera_id: int
        - geo_marker_id: int (optional)
        - confidence_score: float (0.0-1.0)
        - timestamp: str (ISO format, optional)
        - object_image: numpy array or base64 string
        - numberplate_image: numpy array or base64 string (optional)
        - person_image: numpy array or base64 string (optional)
        """
        if not self.auth_token:
            print("✗ No auth token available. Attempting to login...")
            if not self.login():
                return False

        # Validate detection type
        valid_types = ["Fuel Nozzle", "Car", "Bike", "Human", "Truck"]
        detection_type = detection_data.get('detection_type')
        if detection_type not in valid_types:
            print(f"✗ Invalid detection_type: {detection_type}. Must be one of {valid_types}")
            return False

        camera_id = detection_data.get('camera_id')
        confidence_score = detection_data.get('confidence_score', 0.0)
        
        # Check for duplicates
        timestamp = detection_data.get('timestamp', datetime.utcnow().isoformat())
        track_id = detection_data.get('track_id')
        if self.is_duplicate(camera_id, detection_type, timestamp, track_id):
            return False

        # Encode images if they are numpy arrays
        object_image = detection_data.get('object_image')
        if object_image is not None and isinstance(object_image, np.ndarray):
            object_image = self.encode_image_base64(object_image)
        elif object_image is None:
            object_image = ""  # Required field

        numberplate_image = detection_data.get('numberplate_image')
        if numberplate_image is not None and isinstance(numberplate_image, np.ndarray):
            numberplate_image = self.encode_image_base64(numberplate_image)

        person_image = detection_data.get('person_image')
        if person_image is not None and isinstance(person_image, np.ndarray):
            person_image = self.encode_image_base64(person_image)
            
        numberplate_text = detection_data.get('numberplate_text')
        geo_marker_id = detection_data.get('geo_marker_id')

        # Prepare payload matching the new API schema
        payload = {
            "detection_type": detection_type,
            "camera_id": int(camera_id) if camera_id is not None else None,
            "geo_marker_id": geo_marker_id,
            "confidence_score": float(confidence_score),
            "timestamp": timestamp,
            "object_image": object_image,
            "numberplate_image": numberplate_image,
            "numberplate_text": numberplate_text,
            "person_image": person_image,
            "track_id": int(track_id) if track_id is not None else None
        }

        headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json"
        }

        try:
            response = requests.post(
                f"{self.api_base_url}/vehicle/store",
                json=payload,
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                # Update last detection time
                if track_id is not None:
                    key = f"{camera_id}_{detection_type}_{track_id}"
                else:
                    key = f"{camera_id}_{detection_type}"
                self.last_detections[key] = datetime.utcnow()
                
                result = response.json()
                print(f"✓ Detection stored: ID={result.get('id')}, Type={detection_type}, Camera={camera_id}, Confidence={confidence_score:.2f}")
                return True
            elif response.status_code == 404:
                print(f"✗ Camera {camera_id} not found (Deleted). Stopping detection service.")
                return "STOP"
            else:
                error_detail = response.json().get('detail', 'Unknown error')
                print(f"✗ Failed to store detection: {response.status_code} - {error_detail}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"✗ Error sending detection to backend: {e}")
            return False
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
            return False

    def get_active_cameras(self):
        """Get active cameras from backend"""
        if not self.auth_token:
            if not self.login():
                return []

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        try:
            response = requests.get(f"{self.api_base_url}/camera/list", headers=headers, timeout=5)
            if response.status_code == 200:
                cameras = response.json()
                return [cam for cam in cameras if cam.get('status', False)]
            else:
                print(f"✗ Failed to get cameras: {response.status_code}")
                return []
        except Exception as e:
            print(f"✗ Error getting cameras: {e}")
            return []

    def get_geo_markers(self, camera_id):
        """Get geo markers for camera"""
        if not self.auth_token:
            if not self.login():
                return []

        headers = {"Authorization": f"Bearer {self.auth_token}"}

        try:
            response = requests.get(
                f"{self.api_base_url}/geo-marker/by-camera/{camera_id}",
                headers=headers,
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"✗ Failed to get geo markers: {response.status_code}")
                return []
        except Exception as e:
            print(f"✗ Error getting geo markers: {e}")
            return []

    def update_camera_processing_status(self, camera_id, status, completion_message=None):
        """
        Update camera processing status
        status: 'idle', 'processing', 'completed', 'error'
        """
        if not self.auth_token:
            if not self.login():
                return False

        headers = {"Authorization": f"Bearer {self.auth_token}"}
        params = {"processing_status": status}
        if completion_message:
            params["completion_message"] = completion_message

        try:
            response = requests.put(
                f"{self.api_base_url}/camera/processing-status/{camera_id}",
                headers=headers,
                params=params,
                timeout=5
            )
            if response.status_code == 200:
                return True
            else:
                print(f"✗ Failed to update processing status: {response.status_code}")
                return False
        except Exception as e:
            print(f"✗ Error updating processing status: {e}")
            return False


class DetectionProcessor(threading.Thread):
    """Thread for processing detections from video processors"""
    def __init__(self, backend_integration, video_processors):
        super().__init__()
        self.backend = backend_integration
        self.video_processors = video_processors
        self.running = True
        self.daemon = True

    def run(self):
        """Process detections from all video processors"""
        while self.running:
            for processor in self.video_processors:
                detection = processor.get_detection()
                if detection:
                    # Send to backend
                    self.backend.send_detection(detection)
            time.sleep(1)

    def stop(self):
        self.running = False

from pydantic import BaseModel, field_serializer, model_serializer
from typing import Optional
from datetime import datetime

# User schemas
class UserCreate(BaseModel):
    username: str
    password: str
    role: Optional[str] = "admin"

class User(BaseModel):
    id: int
    username: str
    role: str

    class Config:
        from_attributes = True

# Camera schemas
class CameraCreate(BaseModel):
    type: int  # 1 = URL, 2 = MP4
    source: str  # URL or filename

class CameraUpdate(BaseModel):
    status: bool

class Camera(BaseModel):
    id: int
    type: int
    source: str
    status: bool
    processing_status: Optional[str] = "idle"
    completion_message: Optional[str] = None

    class Config:
        from_attributes = True

# Geo Marker schemas
class GeoMarkerCreate(BaseModel):
    camera_id: int
    x1: float
    y1: float
    x2: float
    y2: float

class GeoMarker(BaseModel):
    id: int
    camera_id: int
    x1: float
    y1: float
    x2: float
    y2: float

    class Config:
        from_attributes = True

# Detection schemas (renamed from Vehicle to match spec)
class DetectionCreate(BaseModel):
    detection_type: str  # Fuel Nozzle, Car, Bike, Human, Truck
    camera_id: int
    geo_marker_id: Optional[int] = None
    confidence_score: float
    timestamp: Optional[str] = None
    object_image: str  # base64
    numberplate_image: Optional[str] = None  # base64
    numberplate_text: Optional[str] = None
    person_image: Optional[str] = None  # base64
    track_id: Optional[int] = None

class Detection(BaseModel):
    id: int
    camera_id: int
    geo_marker_id: Optional[int]
    detection_type: str
    confidence_score: float
    object_image: str
    numberplate_image: Optional[str]
    numberplate_text: Optional[str]
    person_image: Optional[str]
    track_id: Optional[int]
    timestamp: str
    status: str

    @field_serializer('timestamp', mode='plain')
    def serialize_timestamp(self, value):
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value) if value else ""

    class Config:
        from_attributes = True  # Pydantic v2 - allows ORM model conversion
        
    @classmethod
    def model_validate(cls, obj, **kwargs):
        """Override model_validate to handle datetime conversion from ORM"""
        if hasattr(obj, '__dict__'):  # It's an ORM object
            data = {
                'id': obj.id,
                'camera_id': obj.camera_id,
                'geo_marker_id': obj.geo_marker_id,
                'detection_type': obj.detection_type,
                'confidence_score': obj.confidence_score,
                'object_image': obj.object_image,
                'numberplate_image': obj.numberplate_image,
                'numberplate_text': obj.numberplate_text,
                'person_image': obj.person_image,
                'track_id': obj.track_id,
                'timestamp': obj.timestamp.isoformat() if isinstance(obj.timestamp, datetime) else obj.timestamp,
                'status': obj.status
            }
            return super().model_validate(data, **kwargs)
        return super().model_validate(obj, **kwargs)

# Keep Vehicle schemas for backward compatibility (aliased to Detection)
VehicleCreate = DetectionCreate
Vehicle = Detection

# Auth schemas
class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

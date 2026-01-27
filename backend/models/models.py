from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, Index
from app.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    password_hash = Column(String)
    role = Column(String, default="admin")

class Camera(Base):
    __tablename__ = "cameras"
    id = Column(Integer, primary_key=True, index=True)
    type = Column(Integer)  # 1 = URL, 2 = MP4
    source = Column(String)  # URL or filename
    status = Column(Boolean, default=True)
    processing_status = Column(String, default="idle")  # idle, processing, completed, error
    completion_message = Column(Text, nullable=True)  # Completion statistics message

class GeoMarker(Base):
    __tablename__ = "geo_markers"
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, index=True)
    x1 = Column(Float)
    y1 = Column(Float)
    x2 = Column(Float)
    y2 = Column(Float)

class Detection(Base):
    __tablename__ = "detections"
    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(Integer, index=True)
    geo_marker_id = Column(Integer, index=True, nullable=True)
    detection_type = Column(String, index=True)  # Fuel Nozzle, Car, Bike, Human, Truck
    confidence_score = Column(Float)
    object_image = Column(Text)  # base64
    numberplate_image = Column(Text, nullable=True)  # base64
    numberplate_text = Column(String, nullable=True)  # Extracted text
    person_image = Column(Text, nullable=True)  # base64
    track_id = Column(Integer, nullable=True, index=True)  # YOLO track ID for advanced tracking
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String, default="active", index=True)  # active / inactive
    
    # Create indexes for performance
    __table_args__ = (
        Index('idx_camera_status', 'camera_id', 'status'),
        Index('idx_type_status', 'detection_type', 'status'),
        Index('idx_timestamp_status', 'timestamp', 'status'),
    )

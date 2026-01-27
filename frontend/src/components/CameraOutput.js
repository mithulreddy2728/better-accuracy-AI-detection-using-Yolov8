import React, { useState, useEffect, useRef } from "react";
import axios from "axios";

const CameraOutput = () => {
  const [cameras, setCameras] = useState([]);
  const [currentCameraIndex, setCurrentCameraIndex] = useState(0);
  const [vehicles, setVehicles] = useState([]);
  const [geoMarkers, setGeoMarkers] = useState([]);
  const videoRef = useRef(null);

  useEffect(() => {
    fetchCameras();
  }, []);

  useEffect(() => {
    if (cameras.length > 0) {
      fetchVehicles(cameras[currentCameraIndex].id);
      fetchGeoMarkers(cameras[currentCameraIndex].id);
      loadVideo(cameras[currentCameraIndex]);
    }
  }, [cameras, currentCameraIndex]);

  // Poll for new vehicle detections every 5 seconds
  useEffect(() => {
    if (cameras.length > 0) {
      const interval = setInterval(() => {
        fetchVehicles(cameras[currentCameraIndex].id);
      }, 5000); // 5 seconds

      return () => clearInterval(interval);
    }
  }, [cameras, currentCameraIndex]);

  const fetchCameras = async () => {
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get("http://localhost:8000/cameras/list", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCameras(response.data.filter((camera) => camera.status));
    } catch (error) {
      console.error("Error fetching cameras:", error);
    }
  };

  const fetchVehicles = async (cameraId) => {
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get(
        `http://localhost:8000/vehicles/by-camera/${cameraId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      setVehicles(response.data);
    } catch (error) {
      console.error("Error fetching vehicles:", error);
    }
  };

  const fetchGeoMarkers = async (cameraId) => {
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get(
        `http://localhost:8000/geo-markers/by-camera/${cameraId}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      setGeoMarkers(response.data);
    } catch (error) {
      console.error("Error fetching geo markers:", error);
    }
  };

  const loadVideo = (camera) => {
    if (videoRef.current) {
      if (camera.type === 1) {
        videoRef.current.src = camera.source;
      } else {
        // For MP4 files, served from backend media directory
        videoRef.current.src = `http://localhost:8000/media/${camera.source}`;
      }
    }
  };

  const nextCamera = () => {
    setCurrentCameraIndex((prevIndex) => (prevIndex + 1) % cameras.length);
  };

  return (
    <div className="camera-output">
      <h3>Camera Output</h3>
      <div className="video-container">
        <video ref={videoRef} controls autoPlay muted>
          Your browser does not support the video tag.
        </video>
        {geoMarkers.map((marker) => (
          <div
            key={marker.id}
            className="geo-marker"
            style={{
              position: "absolute",
              left: `${marker.x1}%`,
              top: `${marker.y1}%`,
              width: `${marker.x2 - marker.x1}%`,
              height: `${marker.y2 - marker.y1}%`,
              border: "2px solid red",
              pointerEvents: "none",
            }}
          />
        ))}
      </div>
      <button onClick={nextCamera}>Next Camera</button>
      <div className="vehicle-data">
        <h4>Detected Vehicles</h4>
        {vehicles.map((vehicle) => (
          <div key={vehicle.id} className="vehicle-item">
            <p>Number: {vehicle.vehicle_number || "Not detected"}</p>
            <p>Timestamp: {vehicle.timestamp}</p>
            {vehicle.vehicle_image && (
              <img
                src={`data:image/jpeg;base64,${vehicle.vehicle_image}`}
                alt="Vehicle"
              />
            )}
            {vehicle.numberplate_image && (
              <img
                src={`data:image/jpeg;base64,${vehicle.numberplate_image}`}
                alt="Number Plate"
              />
            )}
            {vehicle.person_image && (
              <img
                src={`data:image/jpeg;base64,${vehicle.person_image}`}
                alt="Person"
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default CameraOutput;

import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import ImageModal from "./ImageModal";
import ProcessingNotification from "./ProcessingNotification";
import "./DetectionTable.css";

const DetectionTable = ({ detections, onRefresh }) => {
  const [filteredDetections, setFilteredDetections] = useState(detections);
  const [selectedCamera, setSelectedCamera] = useState("all");
  const [selectedType, setSelectedType] = useState("all");
  const [cameras, setCameras] = useState([]);
  const [selectedImage, setSelectedImage] = useState(null);
  const [imageModalOpen, setImageModalOpen] = useState(false);

  useEffect(() => {
    fetchCameras();
  }, []);

  const filterDetections = useCallback(() => {
    let filtered = [...detections];

    if (selectedCamera !== "all") {
      filtered = filtered.filter(d => d.camera_id === parseInt(selectedCamera));
    }

    if (selectedType !== "all") {
      filtered = filtered.filter(d => d.detection_type === selectedType);
    }

    setFilteredDetections(filtered);
  }, [detections, selectedCamera, selectedType]);

  useEffect(() => {
    filterDetections();
  }, [filterDetections]);

  const fetchCameras = async () => {
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get("http://localhost:8000/camera/list", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setCameras(response.data);
    } catch (error) {
      console.error("Error fetching cameras:", error);
    }
  };

  const handleImageClick = (imageData, imageType) => {
    if (imageData) {
      setSelectedImage({ data: imageData, type: imageType });
      setImageModalOpen(true);
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return "N/A";
    try {
      const date = new Date(timestamp);
      return date.toLocaleString();
    } catch {
      return timestamp;
    }
  };

  const detectionTypes = ["Fuel Nozzle", "Car", "Bike", "Human", "Truck"];

  return (
    <div className="detection-table-container">
      <ProcessingNotification />
      <div className="filters">
        <div className="filter-group">
          <label>Filter by Camera:</label>
          <select
            value={selectedCamera}
            onChange={(e) => setSelectedCamera(e.target.value)}
          >
            <option value="all">All Cameras</option>
            {cameras.map((camera) => (
              <option key={camera.id} value={camera.id}>
                Camera {camera.id} - {camera.type === 1 ? "URL" : "MP4"}
              </option>
            ))}
          </select>
        </div>
        <div className="filter-group">
          <label>Filter by Type:</label>
          <select
            value={selectedType}
            onChange={(e) => setSelectedType(e.target.value)}
          >
            <option value="all">All Types</option>
            {detectionTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </div>
        <button onClick={onRefresh} className="refresh-btn">
          Refresh
        </button>
      </div>

      <div className="table-wrapper">
        <table className="detection-table">
          <thead>
            <tr>
              <th>Type</th>
              <th>Vehicle ID</th>
              <th>Confidence</th>
              <th>Camera</th>
              <th>Plate Text</th>
              <th>Timestamp</th>
              <th>Images</th>
            </tr>
          </thead>
          <tbody>
            {filteredDetections.length === 0 ? (
              <tr>
                <td colSpan="7" className="no-data">
                  No detections found
                </td>
              </tr>
            ) : (
              filteredDetections.map((detection) => (
                <tr key={detection.id}>
                  <td>
                    <span className={`type-badge type-${detection.detection_type.toLowerCase().replace(" ", "-")}`}>
                      {detection.detection_type}
                    </span>
                  </td>
                  <td>{detection.track_id ? `#${detection.track_id}` : "N/A"}</td>
                  <td>
                    <div className="confidence-bar">
                      <div
                        className="confidence-fill"
                        style={{ width: `${detection.confidence_score * 100}%` }}
                      />
                      <span className="confidence-text">
                        {(detection.confidence_score * 100).toFixed(1)}%
                      </span>
                    </div>
                  </td>
                  <td>Camera {detection.camera_id}</td>
                  <td className="plate-text-cell">
                    {detection.numberplate_text ? (
                      <span className="plate-text">{detection.numberplate_text}</span>
                    ) : (
                      <span className="no-plate">-no number plate</span>
                    )}
                  </td>
                  <td>{formatTimestamp(detection.timestamp)}</td>
                  <td>
                    <div className="image-buttons">
                      <button
                        className="image-btn"
                        onClick={() => handleImageClick(detection.object_image, "Object")}
                        disabled={!detection.object_image}
                      >
                        Object
                      </button>
                      {detection.numberplate_image && (
                        <button
                          className="image-btn"
                          onClick={() => handleImageClick(detection.numberplate_image, "Number Plate")}
                        >
                          Plate
                        </button>
                      )}
                      {detection.person_image && (
                        <button
                          className="image-btn"
                          onClick={() => handleImageClick(detection.person_image, "Person")}
                        >
                          Person
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {imageModalOpen && selectedImage && (
        <ImageModal
          imageData={selectedImage.data}
          imageType={selectedImage.type}
          onClose={() => {
            setImageModalOpen(false);
            setSelectedImage(null);
          }}
        />
      )}
    </div>
  );
};

export default DetectionTable;


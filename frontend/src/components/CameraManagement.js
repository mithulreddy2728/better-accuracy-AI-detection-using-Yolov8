import React, { useState, useEffect } from "react";
import axios from "axios";
import "./CameraManagement.css";

const CameraManagement = () => {
  const [cameras, setCameras] = useState([]);
  const [newCamera, setNewCamera] = useState({ type: 1, source: "" });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchCameras();
  }, []);

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

  const addCamera = async (e) => {
    e.preventDefault();
    if (!newCamera.source.trim()) {
      alert("Please enter a camera source");
      return;
    }
    
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      await axios.post("http://localhost:8000/camera/add", newCamera, {
        headers: { Authorization: `Bearer ${token}` },
      });
      setNewCamera({ type: 1, source: "" });
      fetchCameras();
    } catch (error) {
      console.error("Error adding camera:", error);
      alert("Error adding camera. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const toggleCameraStatus = async (cameraId, currentStatus) => {
    try {
      const token = localStorage.getItem("token");
      await axios.put(
        `http://localhost:8000/camera/status/${cameraId}`,
        { status: !currentStatus },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      fetchCameras();
    } catch (error) {
      console.error("Error updating camera status:", error);
      alert("Error updating camera status. Please try again.");
    }
  };

  const deleteCamera = async (cameraId) => {
    if (!window.confirm("Are you sure you want to delete this camera and all its detections?")) {
      return;
    }
    try {
      const token = localStorage.getItem("token");
      await axios.delete(`http://localhost:8000/camera/delete/${cameraId}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      fetchCameras();
    } catch (error) {
      console.error("Error deleting camera:", error);
      alert("Error deleting camera. Please try again.");
    }
  };

  return (
    <div className="camera-management">
      <h1>Camera Management</h1>
      
      <div className="add-camera-form">
        <h2>Add New Camera</h2>
        <form onSubmit={addCamera}>
          <div className="form-group">
            <label>Camera Type:</label>
            <select
              value={newCamera.type}
              onChange={(e) =>
                setNewCamera({ ...newCamera, type: parseInt(e.target.value) })
              }
            >
              <option value={1}>Live URL</option>
              <option value={2}>MP4 File</option>
            </select>
          </div>
          <div className="form-group">
            <label>
              {newCamera.type === 1 ? "Camera URL:" : "MP4 Filename:"}
            </label>
            <input
              type="text"
              placeholder={
                newCamera.type === 1
                  ? "Enter RTSP/HTTP URL (e.g., rtsp://example.com/stream)"
                  : "Enter MP4 filename (e.g., sample.mp4)"
              }
              value={newCamera.source}
              onChange={(e) =>
                setNewCamera({ ...newCamera, source: e.target.value })
              }
              required
            />
            {newCamera.type === 2 && (
              <p className="help-text">
                Place MP4 files in the backend/media/ directory. Enter just the filename.
              </p>
            )}
          </div>
          <button type="submit" disabled={loading}>
            {loading ? "Adding..." : "Add Camera"}
          </button>
        </form>
      </div>

      <div className="camera-list-section">
        <h2>Camera List</h2>
        {cameras.length === 0 ? (
          <p className="no-cameras">No cameras added yet.</p>
        ) : (
          <div className="camera-table-wrapper">
            <table className="camera-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Type</th>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {cameras.map((camera) => (
                  <tr key={camera.id}>
                    <td>{camera.id}</td>
                    <td>
                      <span className="type-badge">
                        {camera.type === 1 ? "URL" : "MP4"}
                      </span>
                    </td>
                    <td className="source-cell">{camera.source}</td>
                    <td>
                      <span className={`status-badge ${camera.status ? "active" : "inactive"}`}>
                        {camera.status ? "Active" : "Inactive"}
                      </span>
                    </td>
                    <td>
                      <button
                        className={`toggle-btn ${camera.status ? "deactivate" : "activate"}`}
                        onClick={() => toggleCameraStatus(camera.id, camera.status)}
                      >
                        {camera.status ? "Deactivate" : "Activate"}
                      </button>
                      <button
                        className="delete-camera-btn"
                        onClick={() => deleteCamera(camera.id)}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default CameraManagement;

import React, { useState, useEffect, useCallback, useRef } from "react";
import axios from "axios";
import "./GeoMarking.css";

const GeoMarking = () => {
  const [cameras, setCameras] = useState([]);
  const [selectedCamera, setSelectedCamera] = useState("");
  const [markers, setMarkers] = useState([]);
  const [detections, setDetections] = useState([]);
  const [drawing, setDrawing] = useState(false);
  const [startPos, setStartPos] = useState(null);
  const [currentBox, setCurrentBox] = useState(null);
  const canvasRef = useRef(null);
  const videoRef = useRef(null);
  const containerRef = useRef(null);

  useEffect(() => {
    fetchCameras();
  }, []);

  const drawMarkers = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    markers.forEach(marker => {
      ctx.strokeStyle = "#ff0000";
      ctx.lineWidth = 2;
      ctx.strokeRect(marker.x1, marker.y1, marker.x2 - marker.x1, marker.y2 - marker.y1);
    });
  }, [markers]);

  const fetchMarkers = useCallback(async () => {
    if (!selectedCamera) return;
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get(
        `http://localhost:8000/geo-marker/by-camera/${selectedCamera}`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      setMarkers(response.data);
    } catch (error) {
      console.error("Error fetching markers:", error);
    }
  }, [selectedCamera]);

  useEffect(() => {
    fetchMarkers();
  }, [fetchMarkers]);

  useEffect(() => {
    drawMarkers();
  }, [drawMarkers]);

  // Auto-refresh detections every 3 seconds
  useEffect(() => {
    if (!selectedCamera) return;

    const fetchDetections = async () => {
      try {
        const token = localStorage.getItem("token");
        const response = await axios.get(
          `http://localhost:8000/vehicle/by-camera-geo-fence/${selectedCamera}`,
          {
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        setDetections(response.data);
      } catch (error) {
        console.error("Error fetching detections:", error);
      }
    };

    fetchDetections();
    const interval = setInterval(fetchDetections, 3000);
    return () => clearInterval(interval);
  }, [selectedCamera]);

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

  const loadVideo = (camera) => {
    if (videoRef.current && camera) {
      if (camera.type === 1) {
        videoRef.current.src = camera.source;
      } else {
        videoRef.current.src = `http://localhost:8000/media/${camera.source}`;
      }
    }
  };

  useEffect(() => {
    if (selectedCamera) {
      const camera = cameras.find(c => c.id === parseInt(selectedCamera));
      if (camera) {
        loadVideo(camera);
      }
    }
  }, [selectedCamera, cameras]);

  useEffect(() => {
    if (videoRef.current && canvasRef.current) {
      const video = videoRef.current;
      const canvas = canvasRef.current;

      const updateCanvas = () => {
        canvas.width = video.videoWidth || 800;
        canvas.height = video.videoHeight || 600;
        drawMarkers();
      };

      video.addEventListener("loadedmetadata", updateCanvas);
      return () => video.removeEventListener("loadedmetadata", updateCanvas);
    }
  }, [drawMarkers, selectedCamera]);

  const getMousePos = (e) => {
    const rect = containerRef.current.getBoundingClientRect();
    const video = videoRef.current;
    if (!video) return { x: 0, y: 0 };

    const scaleX = (video.videoWidth || 800) / rect.width;
    const scaleY = (video.videoHeight || 600) / rect.height;

    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY
    };
  };

  const handleMouseDown = (e) => {
    if (!selectedCamera) return;
    const pos = getMousePos(e);
    setDrawing(true);
    setStartPos(pos);
    setCurrentBox({ x1: pos.x, y1: pos.y, x2: pos.x, y2: pos.y });
  };

  const handleMouseMove = (e) => {
    if (!drawing || !startPos) return;
    const pos = getMousePos(e);
    const newBox = {
      x1: Math.min(startPos.x, pos.x),
      y1: Math.min(startPos.y, pos.y),
      x2: Math.max(startPos.x, pos.x),
      y2: Math.max(startPos.y, pos.y)
    };
    setCurrentBox(newBox);

    const canvas = canvasRef.current;
    if (canvas) {
      const ctx = canvas.getContext("2d");
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      drawMarkers();

      ctx.strokeStyle = "#00ff00";
      ctx.lineWidth = 2;
      ctx.strokeRect(newBox.x1, newBox.y1, newBox.x2 - newBox.x1, newBox.y2 - newBox.y1);
    }
  };

  const handleMouseUp = async () => {
    if (!drawing || !currentBox || !selectedCamera) return;

    setDrawing(false);

    // Save marker
    try {
      const token = localStorage.getItem("token");
      await axios.post(
        "http://localhost:8000/geo-marker/add",
        {
          camera_id: parseInt(selectedCamera),
          x1: currentBox.x1,
          y1: currentBox.y1,
          x2: currentBox.x2,
          y2: currentBox.y2,
        },
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      setCurrentBox(null);
      fetchMarkers();
    } catch (error) {
      console.error("Error adding marker:", error);
      alert("Error adding marker. Please try again.");
    }
  };

  return (
    <div className="geo-marking">
      <h1>Geo-Fencing</h1>

      <div className="geo-form">
        <div className="form-group">
          <label>Select Camera:</label>
          <select
            value={selectedCamera}
            onChange={(e) => setSelectedCamera(e.target.value)}
          >
            <option value="">Select a camera</option>
            {cameras.map((camera) => (
              <option key={camera.id} value={camera.id}>
                Camera {camera.id} - {camera.type === 1 ? "URL" : "MP4"}: {camera.source}
              </option>
            ))}
          </select>
        </div>
      </div>

      {selectedCamera && (
        <div className="video-section">
          <h2>Draw ROI (Region of Interest)</h2>
          <p className="instruction-text">
            Click and drag on the video to draw a rectangle ROI box. Release to save.
          </p>
          <div
            className="video-container"
            ref={containerRef}
            onMouseDown={handleMouseDown}
            onMouseMove={handleMouseMove}
            onMouseUp={handleMouseUp}
            onMouseLeave={handleMouseUp}
          >
            <video ref={videoRef} controls muted style={{ width: "100%", maxWidth: "800px" }}>
              Your browser does not support the video tag.
            </video>
            <canvas
              ref={canvasRef}
              className="overlay-canvas"
              style={{ position: "absolute", top: 0, left: 0, pointerEvents: "none" }}
            />
          </div>
        </div>
      )}

      {selectedCamera && markers.length > 0 && (
        <div className="markers-list">
          <h2>Saved Markers</h2>
          <div className="markers-table-wrapper">
            <table className="markers-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>X1</th>
                  <th>Y1</th>
                  <th>X2</th>
                  <th>Y2</th>
                </tr>
              </thead>
              <tbody>
                {markers.map((marker) => (
                  <tr key={marker.id}>
                    <td>{marker.id}</td>
                    <td>{marker.x1.toFixed(1)}</td>
                    <td>{marker.y1.toFixed(1)}</td>
                    <td>{marker.x2.toFixed(1)}</td>
                    <td>{marker.y2.toFixed(1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selectedCamera && (
        <div className="detections-list">
          <h2>Detected Vehicles in Geo-Fences</h2>
          <p className="info-text">
            Showing vehicles detected within geo-fenced areas (auto-refreshes every 3 seconds)
          </p>

          {detections.length > 0 ? (
            <div className="detections-grid">
              {detections.map((detection) => (
                <div key={detection.id} className="detection-card">
                  <div className="detection-header">
                    <span className="detection-type">{detection.detection_type}</span>
                    <span className="detection-fence">Geo-Fence #{detection.geo_marker_id}</span>
                  </div>
                  {detection.object_image && (
                    <img
                      src={detection.object_image}
                      alt={detection.detection_type}
                      className="detection-image"
                    />
                  )}
                  <div className="detection-info">
                    <div className="info-row">
                      <strong>Vehicle ID:</strong> {detection.track_id || detection.id}
                    </div>
                    <div className="info-row">
                      <strong>License Plate:</strong>
                      <span className={detection.numberplate_text ? "plate-text" : "no-plate"}>
                        {detection.numberplate_text || "Not detected"}
                      </span>
                    </div>
                    {detection.numberplate_image && (
                      <div className="plate-image-container">
                        <img
                          src={detection.numberplate_image}
                          alt="License Plate"
                          className="plate-image"
                        />
                      </div>
                    )}
                    <div className="info-row">
                      <strong>Confidence:</strong> {(detection.confidence_score * 100).toFixed(1)}%
                    </div>
                    <div className="info-row timestamp">
                      {new Date(detection.timestamp).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="no-detections-message">
              <p>⏳ <strong>No detections in geo-fenced areas yet.</strong></p>
              {markers.length > 0 ? (
                <div className="status-info">
                  <p>✓ You have {markers.length} geo-fence(s) configured.</p>
                  <p>💡 <strong>To see detections:</strong></p>
                  <ol style={{ textAlign: 'left', display: 'inline-block', marginTop: '10px' }}>
                    <li>Go to the <strong>Cameras</strong> page</li>
                    <li>Delete and re-add Camera {selectedCamera} to reload geo-fences</li>
                    <li>Wait for objects to enter the geo-fenced area</li>
                    <li>Detections will appear here automatically</li>
                  </ol>
                </div>
              ) : (
                <p>⚠️ Please draw a geo-fence ROI above to start detecting objects.</p>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default GeoMarking;

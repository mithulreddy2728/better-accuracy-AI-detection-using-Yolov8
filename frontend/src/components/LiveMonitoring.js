import React, { useState, useEffect } from "react";
import axios from "axios";
import "./LiveMonitoring.css";

const LiveMonitoring = () => {
    const [cameras, setCameras] = useState([]);
    const [selectedCamera, setSelectedCamera] = useState("");
    const [streamUrl, setStreamUrl] = useState("");
    const [isStreaming, setIsStreaming] = useState(false);

    // ROI Drawing States
    const [isDrawingMode, setIsDrawingMode] = useState(false);
    const [drawing, setDrawing] = useState(false);
    const [startPos, setStartPos] = useState(null);
    const [currentBox, setCurrentBox] = useState(null);
    const canvasRef = React.useRef(null);
    const containerRef = React.useRef(null);
    const imageRef = React.useRef(null);

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

    const startStream = () => {
        if (!selectedCamera) return;
        const token = localStorage.getItem("token");
        setStreamUrl(`http://localhost:8000/live-feed/${selectedCamera}?token=${token}`);
        setIsStreaming(true);
    };

    const stopStream = () => {
        setStreamUrl("");
        setIsStreaming(false);
        setIsDrawingMode(false);
    };

    // ROI Drawing Logic
    const getMousePos = (e) => {
        if (!containerRef.current || !imageRef.current) return { x: 0, y: 0 };
        const rect = containerRef.current.getBoundingClientRect();
        const img = imageRef.current;

        // Scale mouse position to actual image dimensions
        const scaleX = img.naturalWidth / rect.width;
        const scaleY = img.naturalHeight / rect.height;

        return {
            x: (e.clientX - rect.left) * scaleX,
            y: (e.clientY - rect.top) * scaleY
        };
    };

    const handleMouseDown = (e) => {
        if (!isDrawingMode || !isStreaming) return;
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
        drawPreview(newBox);
    };

    const drawPreview = (box) => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        // Draw the current box being drawn
        ctx.strokeStyle = "#00ff00";
        ctx.lineWidth = 3;
        ctx.strokeRect(box.x1, box.y1, box.x2 - box.x1, box.y2 - box.y1);

        // Add "New ROI" label
        ctx.fillStyle = "#00ff00";
        ctx.font = "bold 16px Inter";
        ctx.fillText("NEW ROI", box.x1, box.y1 - 10);
    };

    const handleMouseUp = async () => {
        if (!drawing || !currentBox) return;
        setDrawing(false);

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

            // Clear preview
            const canvas = canvasRef.current;
            if (canvas) {
                const ctx = canvas.getContext("2d");
                ctx.clearRect(0, 0, canvas.width, canvas.height);
            }
            setCurrentBox(null);
            alert("ROI Added Successfully! The system will now prioritize objects in this box.");
        } catch (error) {
            console.error("Error adding ROI:", error);
            alert("Failed to save ROI.");
        }
    };

    const handleImageLoad = () => {
        if (imageRef.current && canvasRef.current) {
            canvasRef.current.width = imageRef.current.naturalWidth;
            canvasRef.current.height = imageRef.current.naturalHeight;
        }
    };

    return (
        <div className="live-monitoring">
            <div className="monitoring-header">
                <h1>Real-Time Live Monitoring</h1>
                {isStreaming && (
                    <button
                        className={`roi-toggle-btn ${isDrawingMode ? 'active' : ''}`}
                        onClick={() => setIsDrawingMode(!isDrawingMode)}
                    >
                        {isDrawingMode ? "Cancel Drawing" : "Draw ROI Box"}
                    </button>
                )}
            </div>

            <div className="monitoring-controls">
                <div className="form-group">
                    <label>Select Camera:</label>
                    <select
                        value={selectedCamera}
                        onChange={(e) => setSelectedCamera(e.target.value)}
                        disabled={isStreaming}
                    >
                        <option value="">Choose a camera...</option>
                        {cameras.map((camera) => (
                            <option key={camera.id} value={camera.id}>
                                Camera {camera.id} - {camera.source}
                            </option>
                        ))}
                    </select>
                </div>

                {!isStreaming ? (
                    <button className="start-btn" onClick={startStream} disabled={!selectedCamera}>
                        Start Live Monitoring
                    </button>
                ) : (
                    <button className="stop-btn" onClick={stopStream}>
                        Stop Monitoring
                    </button>
                )}
            </div>

            <div className="stream-display">
                {isStreaming ? (
                    <div
                        className={`video-wrapper ${isDrawingMode ? 'drawing-active' : ''}`}
                        ref={containerRef}
                        onMouseDown={handleMouseDown}
                        onMouseMove={handleMouseMove}
                        onMouseUp={handleMouseUp}
                        onMouseLeave={() => setDrawing(false)}
                    >
                        <img
                            src={streamUrl}
                            alt="Live Stream"
                            className="live-video-feed"
                            ref={imageRef}
                            onLoad={handleImageLoad}
                            onError={() => {
                                alert("Failed to connect to stream.");
                                stopStream();
                            }}
                        />
                        <canvas
                            ref={canvasRef}
                            className="drawing-canvas"
                        />
                        <div className="stream-overlay">
                            <span className="live-badge">LIVE</span>
                            <span className="camera-info">Camera ID: {selectedCamera}</span>
                            {isDrawingMode && <span className="drawing-badge">DRAWING MODE: Click & Drag to add ROI</span>}
                        </div>
                    </div>
                ) : (
                    <div className="placeholder-display">
                        <div className="placeholder-content">
                            <div className="icon-video-slash">🎥</div>
                            <p>Select a camera and click "Start" to view live processed feed</p>
                            <span className="feature-note highlight">
                                HIGH-PRECISION YOLOv8x ENABLED
                            </span>
                        </div>
                    </div>
                )}
            </div>

            <div className="monitoring-info">
                <h3>Live Monitoring Interface</h3>
                <div className="info-grid">
                    <div className="info-item">
                        <span className="bullet green"></span>
                        <p><strong>ROI Detection:</strong> Draw boxes to highlight objects in specific areas.</p>
                    </div>
                    <div className="info-item">
                        <span className="bullet yellow"></span>
                        <p><strong>Precision ANPR:</strong> Advanced YOLOv8x + Specialized Plate Model.</p>
                    </div>
                    <div className="info-item">
                        <span className="bullet red"></span>
                        <p><strong>Object Range:</strong> Car, Truck, Bike, Nozzle, Human.</p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default LiveMonitoring;

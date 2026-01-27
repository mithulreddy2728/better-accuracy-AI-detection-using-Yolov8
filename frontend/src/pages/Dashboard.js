import React, { useState, useEffect } from "react";
import axios from "axios";
import CameraManagement from "../components/CameraManagement";
import GeoMarking from "../components/GeoMarking";
import LiveMonitoring from "../components/LiveMonitoring";
import DetectionTable from "../components/DetectionTable";
import VideoUpload from "../components/VideoUpload";
import "./Dashboard.css";

const Dashboard = ({ onLogout }) => {
  const [activeTab, setActiveTab] = useState("detections");
  const [detections, setDetections] = useState([]);
  const [stats, setStats] = useState({
    total: 0,
    active: 0,
    byType: {},
  });

  useEffect(() => {
    let interval;
    if (activeTab === "detections") {
      fetchDetections();
      // Auto-refresh every 5 seconds
      interval = setInterval(fetchDetections, 5000);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [activeTab]);

  const fetchDetections = async () => {
    try {
      const token = localStorage.getItem("token");
      const response = await axios.get("http://localhost:8000/vehicle/active", {
        headers: { Authorization: `Bearer ${token}` },
      });
      setDetections(response.data);

      // Calculate stats
      const activeCount = response.data.length;
      const byType = {};
      response.data.forEach((det) => {
        byType[det.detection_type] = (byType[det.detection_type] || 0) + 1;
      });

      setStats({
        total: response.data.length,
        active: activeCount,
        byType,
      });
    } catch (error) {
      console.error("Error fetching detections:", error);
    }
  };

  return (
    <div className="dashboard">
      <div className="sidebar">
        <div className="sidebar-header">
          <h2>AI Detection System</h2>
        </div>
        <nav className="sidebar-nav">
          <button
            className={activeTab === "detections" ? "active" : ""}
            onClick={() => setActiveTab("detections")}
          >
            Detections
          </button>
          <button
            className={activeTab === "upload" ? "active" : ""}
            onClick={() => setActiveTab("upload")}
          >
            Upload Video
          </button>
          <button
            className={activeTab === "cameras" ? "active" : ""}
            onClick={() => setActiveTab("cameras")}
          >
            Cameras
          </button>
          <button
            className={activeTab === "geo-marking" ? "active" : ""}
            onClick={() => setActiveTab("geo-marking")}
          >
            Geo-Fencing
          </button>
          <button
            className={activeTab === "live-monitoring" ? "active" : ""}
            onClick={() => setActiveTab("live-monitoring")}
          >
            Live Monitoring
          </button>
          <button className="logout-btn" onClick={onLogout}>
            Logout
          </button>
        </nav>
      </div>
      <div className="main-content">
        {activeTab === "detections" && (
          <div className="detections-view">
            <h1>Detection Dashboard</h1>
            <div className="stats-cards">
              <div className="stat-card">
                <div className="stat-value">{stats.total}</div>
                <div className="stat-label">Total Detections</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.active}</div>
                <div className="stat-label">Active Detections</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">
                  {stats.byType["Fuel Nozzle"] || 0}
                </div>
                <div className="stat-label">Fuel Nozzles</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.byType["Car"] || 0}</div>
                <div className="stat-label">Cars</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.byType["Bike"] || 0}</div>
                <div className="stat-label">Bikes</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.byType["Human"] || 0}</div>
                <div className="stat-label">Humans</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{stats.byType["Truck"] || 0}</div>
                <div className="stat-label">Trucks</div>
              </div>
            </div>
            <div className="detections-actions">
              <button
                className="delete-all-detections-btn"
                onClick={async () => {
                  if (
                    !window.confirm(
                      "Delete ALL detections? This cannot be undone."
                    )
                  )
                    return;
                  try {
                    const token = localStorage.getItem("token");
                    await axios.delete(
                      "http://localhost:8000/vehicle/delete-all",
                      {
                        headers: { Authorization: `Bearer ${token}` },
                      }
                    );
                    await fetchDetections();
                  } catch (error) {
                    console.error("Error deleting detections:", error);
                    alert("Failed to delete detections. Please try again.");
                  }
                }}
              >
                Delete All Detections
              </button>
            </div>
            <DetectionTable
              detections={detections}
              onRefresh={fetchDetections}
            />
          </div>
        )}
        {activeTab === "upload" && (
          <VideoUpload
            onUploadSuccess={() => {
              // Refresh detections after upload
              if (activeTab === "detections") {
                fetchDetections();
              }
            }}
          />
        )}
        {activeTab === "cameras" && <CameraManagement />}
        {activeTab === "geo-marking" && <GeoMarking />}
        {activeTab === "live-monitoring" && <LiveMonitoring />}
      </div>
    </div>
  );
};

export default Dashboard;

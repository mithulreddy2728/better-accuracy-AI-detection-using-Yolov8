import React, { useState } from "react";
import axios from "axios";
import "./VideoUpload.css";

const VideoUpload = ({ onUploadSuccess }) => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    if (file) {
      // Validate file type
      const allowedTypes = [
        "video/mp4",
        "video/avi",
        "video/quicktime",
        "video/x-msvideo",
      ];
      if (
        !allowedTypes.includes(file.type) &&
        !file.name.match(/\.(mp4|avi|mov|mkv|webm)$/i)
      ) {
        setError("Please select a video file (MP4, AVI, MOV, MKV, or WEBM)");
        setSelectedFile(null);
        return;
      }
      setError("");
      setSelectedFile(file);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError("Please select a file first");
      return;
    }

    setUploading(true);
    setError("");
    setUploadProgress(0);

    try {
      const token = localStorage.getItem("token");
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await axios.post(
        "http://localhost:8000/upload/video",
        formData,
        {
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "multipart/form-data",
          },
          onUploadProgress: (progressEvent) => {
            const percentCompleted = Math.round(
              (progressEvent.loaded * 100) / progressEvent.total
            );
            setUploadProgress(percentCompleted);
          },
        }
      );

      setUploadProgress(100);
      setSelectedFile(null);

      // Reset file input
      const fileInput = document.getElementById("video-file-input");
      if (fileInput) fileInput.value = "";

      if (onUploadSuccess) {
        onUploadSuccess(response.data);
      }

      alert("Video uploaded successfully! Detection will start automatically.");
    } catch (err) {
      const errorMsg =
        err.response?.data?.detail || err.message || "Upload failed";
      setError(errorMsg);
      console.error("Upload error:", err);
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  return (
    <div className="video-upload">
      <h2>Upload Video</h2>
      <p className="upload-description">
        Upload a video file to automatically start detection. The video will be
        saved and processed in the background.
      </p>

      <div className="upload-section">
        <div className="file-input-wrapper">
          <input
            id="video-file-input"
            type="file"
            accept="video/mp4,video/avi,video/mov,video/mkv,video/webm"
            onChange={handleFileChange}
            disabled={uploading}
            className="file-input"
          />
          <label htmlFor="video-file-input" className="file-label">
            {selectedFile ? selectedFile.name : "Choose Video File"}
          </label>
        </div>

        {selectedFile && (
          <div className="file-info">
            <p>File: {selectedFile.name}</p>
            <p>Size: {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB</p>
          </div>
        )}

        {error && <div className="error-message">{error}</div>}

        {uploading && (
          <div className="upload-progress">
            <div className="progress-bar">
              <div
                className="progress-fill"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
            <p>Uploading... {uploadProgress}%</p>
          </div>
        )}

        <button
          onClick={handleUpload}
          disabled={!selectedFile || uploading}
          className="upload-button"
        >
          {uploading ? "Uploading..." : "Upload & Start Detection"}
        </button>
      </div>
    </div>
  );
};

export default VideoUpload;

import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { getApiUrl } from '../config';
import './ProcessingNotification.css';

const ProcessingNotification = () => {
    const [cameras, setCameras] = useState([]);
    const [completedCameras, setCompletedCameras] = useState(new Set());

    useEffect(() => {
        // Poll for camera status every 3 seconds
        const interval = setInterval(fetchCameraStatus, 3000);
        fetchCameraStatus(); // Initial fetch

        return () => clearInterval(interval);
    }, []);

    const fetchCameraStatus = async () => {
        try {
            const token = localStorage.getItem('token');
            const response = await axios.get(getApiUrl('/camera/list'), {
                headers: { Authorization: `Bearer ${token}` },
            });

            const cameraList = response.data;
            setCameras(cameraList);

            // Track which cameras have been shown as completed
            const newCompleted = new Set(completedCameras);
            cameraList.forEach(camera => {
                if (camera.processing_status === 'completed' && !completedCameras.has(camera.id)) {
                    newCompleted.add(camera.id);
                }
            });
            setCompletedCameras(newCompleted);

        } catch (error) {
            console.error('Error fetching camera status:', error);
        }
    };

    const dismissNotification = (cameraId) => {
        setCompletedCameras(prev => {
            const newSet = new Set(prev);
            newSet.delete(cameraId);
            return newSet;
        });
    };

    const completedCamerasList = cameras.filter(
        camera => camera.processing_status === 'completed' && completedCameras.has(camera.id)
    );

    if (completedCamerasList.length === 0) {
        return null;
    }

    return (
        <div className="processing-notifications">
            {completedCamerasList.map(camera => (
                <div key={camera.id} className="notification notification-success">
                    <div className="notification-icon">✓</div>
                    <div className="notification-content">
                        <div className="notification-title">
                            Video Processing Complete - Camera {camera.id}
                        </div>
                        <div className="notification-message">
                            {camera.completion_message || 'Processing completed successfully'}
                        </div>
                    </div>
                    <button
                        className="notification-close"
                        onClick={() => dismissNotification(camera.id)}
                        aria-label="Dismiss"
                    >
                        ×
                    </button>
                </div>
            ))}
        </div>
    );
};

export default ProcessingNotification;

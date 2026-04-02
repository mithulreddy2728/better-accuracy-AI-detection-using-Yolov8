import React from "react";
import "./ImageModal.css";

const ImageModal = ({ imageData, imageType, onClose }) => {
  const imageSrc = imageData.startsWith("data:image") 
    ? imageData 
    : `data:image/jpeg;base64,${imageData}`;

  return (
    <div className="image-modal-overlay" onClick={onClose}>
      <div className="image-modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="image-modal-header">
          <h3>{imageType} Image</h3>
          <button className="close-btn" onClick={onClose}>×</button>
        </div>
        <div className="image-modal-body">
          <img src={imageSrc} alt={imageType} />
        </div>
      </div>
    </div>
  );
};

export default ImageModal;


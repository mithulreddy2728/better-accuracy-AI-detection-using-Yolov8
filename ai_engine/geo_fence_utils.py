"""
Geo-fence utility functions for checking if detections are within geo-fenced areas
"""

def check_in_geo_fence(bbox, geo_fences):
    """Check if bounding box center is within any geo-fence
    
    Args:
        bbox: [x1, y1, x2, y2] bounding box coordinates
        geo_fences: List of geo-fence dictionaries with x1, y1, x2, y2, id
        
    Returns:
        geo_marker_id if inside a fence, None otherwise
    """
    if not geo_fences:
        return None
    
    # Calculate center point of bounding box
    center_x = (bbox[0] + bbox[2]) / 2
    center_y = (bbox[1] + bbox[3]) / 2
    
    # Check each geo-fence
    for fence in geo_fences:
        if (fence['x1'] <= center_x <= fence['x2'] and 
            fence['y1'] <= center_y <= fence['y2']):
            return fence['id']
    
    return None

def draw_geo_fences(frame, geo_fences):
    """Draw geo-fences on the frame for visualization"""
    import cv2
    for fence in geo_fences:
        x1, y1, x2, y2 = int(fence['x1']), int(fence['y1']), int(fence['x2']), int(fence['y2'])
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 255), 2)  # Yellow
        cv2.putText(frame, f"Fence {fence['id']}", (x1, y1 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    return frame

def draw_detections(frame, bbox, detection_type, track_id=None, plate_text=None, in_fence=False):
    """Draw detection boxes and labels on the frame with premium styling"""
    import cv2
    x1, y1, x2, y2 = map(int, bbox)
    
    # Color: Vibrant Green if in fence, Bright Red otherwise
    color = (0, 255, 0) if in_fence else (0, 0, 255)
    
    # Thicker box for premium feel
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
    
    label = f"{detection_type.upper()}"
    if track_id is not None:
        label += f" #{track_id}"
    if plate_text:
        label += f" | {plate_text}"
        
    # Premium Label Background
    font = cv2.FONT_HERSHEY_DUPLEX
    font_scale = 0.7
    thickness = 2
    (label_width, label_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
    
    # Label background rectangle
    cv2.rectangle(frame, (x1, y1 - label_height - 15), (x1 + label_width + 10, y1), color, -1)
    # Label text (Black for contrast)
    cv2.putText(frame, label, (x1 + 5, y1 - 10), 
                font, font_scale, (0, 0, 0), thickness, cv2.LINE_AA)
    
    return frame
def draw_plate_highlight(frame, bbox, plate_text=None):
    """Draw a specific highlight for the license plate"""
    import cv2
    x1, y1, x2, y2 = map(int, bbox)
    
    # Use a vibrant Cyan for plates (highly visible)
    color = (255, 255, 0)  # Cyan in BGR (was yellow)
    
    # Draw a THICK rectangle for the plate (increased from 3 to 4)
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 4)
    
    if plate_text:
        # Draw a background for the text to make it readable
        label = plate_text
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.7  # Increased from 0.5 for better visibility
        thickness = 2
        (label_width, label_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
        
        # Ensure label doesn't go off screen
        label_y = max(y1, label_height + 10)
        
        # Draw background rectangle
        cv2.rectangle(frame, (x1, label_y - label_height - 10), (x1 + label_width + 10, label_y), color, -1)
        cv2.putText(frame, label, (x1 + 5, label_y - 5), 
                    font, font_scale, (0, 0, 0), thickness)  # Black text on cyan background
    else:
        # If no text, show "Detecting..." to indicate plate detection is active
        label = "Plate Detected"
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        thickness = 2
        (label_width, label_height), baseline = cv2.getTextSize(label, font, font_scale, thickness)
        label_y = max(y1, label_height + 10)
        cv2.rectangle(frame, (x1, label_y - label_height - 10), (x1 + label_width + 10, label_y), color, -1)
        cv2.putText(frame, label, (x1 + 5, label_y - 5), 
                    font, font_scale, (0, 0, 0), thickness)
    return frame

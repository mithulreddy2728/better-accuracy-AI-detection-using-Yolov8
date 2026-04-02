# Advanced ANPR & Multi-Object Detection System

A production-ready AI system for **Automatic Number Plate Recognition (ANPR)**, **multi-vehicle tracking**, and **object detection** with real-time web dashboard visualization.

## 🎯 Overview

This system combines YOLOv8 object detection with advanced tracking algorithms to provide:
- **Multi-vehicle tracking** with unique IDs for each vehicle
- **Accurate license plate detection and OCR** using specialized models
- **Real-time Live Monitoring**: Processed MJPEG stream with AI overlays
- **Enhanced Geo-Fencing**: Automatic ANPR and object tagging for Region of Interest (ROI)
- **Real-time detection** of Cars, Trucks, Bikes, Humans, and Fuel Nozzles
- **Web-based dashboard** for monitoring and management
- **GPU acceleration** support for faster processing

## ✨ Key Features

### 🚗 Advanced Vehicle Tracking
- **Unique Track IDs**: Each vehicle gets a persistent ID throughout the video
- **Multi-vehicle support**: Handles multiple vehicles simultaneously
- **Intelligent merging**: Prevents duplicate detections for the same vehicle

### 🔢 Accurate License Plate Recognition
- **Two-stage detection**: Vehicle detection → Plate localization → OCR
- **Specialized YOLO model** for plate detection (optional but recommended)
- **Fallback OCR mode**: Works without specialized model (lower accuracy)
- **Best plate tracking**: Maintains the highest confidence plate reading per vehicle

### 📊 Web Dashboard
- **Real-time updates**: Auto-refresh detection table every 5 seconds
- **Image preview**: View vehicle, plate, and person crops
- **Vehicle ID display**: See unique tracking IDs for each vehicle
- **Filtering**: Filter by camera, detection type, or search
- **Live Monitoring**: View real-time processed streams with AI overlays
- **Geo-fencing**: Draw areas of interest (ROI) and monitor detections within them in real-time

### ⚡ Performance
- **GPU acceleration**: CUDA support for YOLO and OCR
- **Efficient processing**: Frame skipping and optimized inference
- **Background processing**: Non-blocking detection service

## 🛠️ Prerequisites

### System Requirements
- **Operating System**: Windows 10/11, Linux, or macOS
- **Python**: 3.8 or higher
- **Node.js**: 14 or higher
- **RAM**: Minimum 8GB (16GB recommended)
- **GPU**: Optional but recommended (NVIDIA with CUDA support)

### Software Dependencies
- **Python packages**: Listed in `backend/requirements.txt`
- **Node packages**: Listed in `frontend/package.json`

## 📦 Installation

### Step 1: Clone or Download the Project
```bash
cd c:/projects/nozz
```

### Step 2: Set Up Python Virtual Environment (Recommended)
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Windows (CMD):
.venv\Scripts\activate.bat

# Linux/Mac:
source .venv/bin/activate
```

### Step 3: Install Backend Dependencies
```bash
cd backend
pip install -r requirements.txt
```

**Key Dependencies:**
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `ultralytics` - YOLOv8 implementation
- `easyocr` - OCR engine
- `torch` - Deep learning framework
- `opencv-python-headless` - Computer vision
- `sqlalchemy` - Database ORM

### Step 4: Install Frontend Dependencies
```bash
cd ../frontend
npm install
```

### Step 5: Download License Plate Model (Optional but Recommended)

For **significantly better** license plate detection accuracy:

**Option A - Hugging Face (Easiest):**
1. Visit: https://huggingface.co/AZIIIIIIIIZ/License-plate-detection/blob/main/best.pt
2. Click the Download button
3. Rename to `license_plate.pt`
4. Place in: `c:/projects/nozz/ai_engine/models/license_plate.pt`

**Option B - Use Download Script:**
```bash
cd ../ai_engine
python download_plate_model.py
```

**Note**: The system works without this model (OCR-only mode), but accuracy will be lower.

## 🚀 Running the System

You need **2 terminal windows** running simultaneously.

### Terminal 1: Backend Server

```bash
# Navigate to backend
cd c:/projects/nozz/backend

# Activate virtual environment (if using)
.venv\Scripts\Activate.ps1

# Start the server
python -m uvicorn main:app --reload
```

**Server will start at**: http://localhost:8000

**Expected output:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

### Terminal 2: Frontend Dashboard

```bash
# Navigate to frontend
cd c:/projects/nozz/frontend

# Start the React app
npm start
```

**Dashboard will open at**: http://localhost:3000

**Expected output:**
```
Compiled successfully!
You can now view frontend in the browser.
  Local:            http://localhost:3000
```

## � Usage Guide

### 1. Login to Dashboard
- **URL**: http://localhost:3000
- **Default Credentials**:
  - Username: `admin`
  - Password: `admin`

### 2. Upload Video for Detection

1. Click **"Upload Video"** in the sidebar
2. Select a video file (MP4, AVI, MOV, MKV, WEBM)
3. Click **"Upload & Start Detection"**
4. The system will:
   - Upload the video to `backend/media/`
   - Create a camera entry
   - Start detection in the background
   - Process frames and send detections to the database

### 3. View Detections

1. Click **"Detections"** in the sidebar
2. The table shows:
   - **Vehicle ID**: Unique tracking ID for each vehicle
   - **Type**: Car, Truck, Bike, Human, or Fuel Nozzle
   - **Camera**: Camera ID
   - **Plate Text**: License plate number (or "-no number plate")
   - **Confidence**: Detection confidence score
   - **Timestamp**: When detected
3. Click image buttons to view:
   - **Object**: Full vehicle/object crop
   - **Plate**: License plate crop (if detected)
   - **Person**: Person crop (if applicable)

### 4. Monitor Logs

Check detection progress in real-time:
```bash
# View logs
cat backend/detection_service.log

# Or on Windows
type backend\detection_service.log
```

**Expected log entries:**
```
✓ AI Engine authenticated successfully
🚀 Using device: cuda  (or cpu)
✓ Main YOLO model loaded: yolov8n.pt
✓ License Plate model loaded: Local Model
✓ OCR initialized
✓ Video opened: 3840x2160 @ 30fps
🚀 [Track 1] Car Sent! Plate: ABC1234
🚀 [Track 2] Car Sent! Plate: -no plate-
```

### 5. Manage Detections

- **Delete All**: Click "Delete All Detections" to clear the database
- **Auto-expire**: Detections older than 1 hour are automatically marked inactive
- **Filter**: Use search box or type filters to find specific detections

### 6. Live Monitoring & Geo-Fencing

1. Click **"Geo-Fencing"** in the sidebar:
   - Select a camera
   - Click and drag on the video to draw a **Region of Interest (ROI)**
   - The system will save this area as a geo-fenced marker
2. Click **"Live Monitoring"** in the sidebar:
   - Select your camera and click **"Start Live Monitoring"**
   - You will see the **Live Processed Stream**:
     - Objects inside the ROI are highlighted in **Green**
     - Objects outside the ROI are marked in **Red**
     - **Live ANPR**: License plates are automatically detected and displayed for any vehicle entering the ROI area

## 🏗️ Project Structure

```
c:/projects/nozz/
├── backend/                          # FastAPI Backend Server
│   ├── main.py                       # Application entry point
│   ├── requirements.txt              # Python dependencies
│   ├── nozzle_detection.db          # SQLite database
│   ├── detection_service.log        # Detection logs
│   ├── media/                       # Uploaded videos
│   ├── app/
│   │   ├── database.py              # Database configuration
│   │   └── process_manager.py       # Background process management
│   ├── auth/
│   │   └── auth.py                  # JWT authentication
│   ├── models/
│   │   └── models.py                # SQLAlchemy models
│   ├── schemas/
│   │   └── schemas.py               # Pydantic schemas
│   └── routers/
│       ├── auth.py                  # Login endpoints
│       ├── cameras.py               # Camera management
│       ├── vehicles.py              # Detection storage/retrieval
│       ├── geo_markers.py           # Geo-fencing
│       ├── upload.py                # Video upload
│       └── live_feed.py             # MJPEG streaming with AI overlays
│
├── frontend/                         # React Dashboard
│   ├── package.json                 # Node dependencies
│   ├── public/
│   └── src/
│       ├── App.js                   # Main app component
│       ├── components/
│       │   ├── DetectionTable.js    # Detection display
│       │   ├── VideoUpload.js       # Upload interface
│       │   └── ...
│       └── pages/
│           └── Dashboard.js         # Main dashboard
│
├── ai_engine/                        # AI Detection Engine
│   ├── detection_service.py         # Main detection script
│   ├── backend_integration.py       # API communication
│   ├── download_plate_model.py      # Model download utility
│   └── models/
│       ├── README.md                # Model setup guide
│       └── license_plate.pt         # Plate detection model (optional)
│
└── README.md                         # This file
```

## 🤖 AI Engine Details

### Detection Pipeline

1. **Video Input**: Reads video frame-by-frame
2. **Object Detection**: YOLOv8 detects vehicles, humans, nozzles
3. **Tracking**: Assigns unique Track IDs using BoTSORT/ByteTrack
4. **Plate Detection**: 
   - If specialized model: Detects plate region in vehicle crop
   - If OCR-only: Uses entire vehicle crop
5. **OCR**: EasyOCR reads text from plate region
6. **Aggregation**: Maintains best plate reading per Track ID
7. **Backend Sync**: Sends detections to API every 2 seconds per vehicle

### Models Used

**Primary Object Detector:**
- Model: `yolov8n.pt` (COCO pre-trained)
- Classes: car, truck, bus, motorcycle, person
- Device: CUDA (if available) or CPU

**License Plate Detector (Optional):**
- Model: `ai_engine/models/license_plate.pt`
- Purpose: Accurate plate localization
- Fallback: OCR-only mode if not present

**OCR Engine:**
- Engine: EasyOCR
- Language: English
- GPU: Enabled if CUDA available

### Configuration

**Frame Processing:**
- Interval: Every 2nd frame (configurable in `detection_service.py`)
- Reason: Balance between speed and accuracy

**Detection Rate Limiting:**
- Per vehicle: 2 seconds minimum between updates
- Reason: Reduce redundant API calls

**Plate Confidence Tracking:**
- Strategy: Keep highest confidence plate per Track ID
- Benefit: Prevents low-quality reads from overwriting good ones

## 🔧 Configuration & Customization

### Backend Configuration

**Environment Variables** (create `backend/.env`):
```env
DATABASE_URL=sqlite:///./nozzle_detection.db
SECRET_KEY=your-secret-key-here
```

**Change Default Credentials** (`backend/routers/auth.py`):
```python
# Line ~20
if username == "admin" and password == "admin":
```

### AI Engine Configuration

**Adjust Frame Processing** (`ai_engine/detection_service.py`):
```python
# Line ~146
process_interval = 2  # Process every Nth frame
```

**Change Detection Rate** (`ai_engine/detection_service.py`):
```python
# Line ~238
if should_send or (now - current_record['last_sent'] > 2):  # Seconds
```

**Modify Duplicate Window** (`ai_engine/backend_integration.py`):
```python
# Line ~13
self.duplicate_window = 0.5  # Seconds
```

## 🐛 Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **"No module named 'cv2'"** | Install OpenCV: `pip install opencv-python-headless` |
| **"CUDA not available"** | System will use CPU (slower but works). Install CUDA toolkit for GPU support. |
| **"Port 8000 already in use"** | Stop other services or change port in uvicorn command |
| **"Port 3000 already in use"** | Stop other React apps or change in `package.json` |
| **Database schema errors** | Delete `backend/nozzle_detection.db` and restart backend |
| **No detections appearing** | Check `backend/detection_service.log` for errors |
| **Plate detection not working** | Download specialized model (see Installation Step 5) |
| **"Track ID" column missing** | Run: `python backend/fix_schema.py` (if exists) or delete DB |

### Performance Issues

**Slow Processing:**
- Reduce `process_interval` in `detection_service.py`
- Use GPU (CUDA) if available
- Use smaller video resolution

**High Memory Usage:**
- Reduce video resolution
- Increase `process_interval`
- Close other applications

### Debugging

**Enable Verbose Logging:**
```python
# In detection_service.py, line ~24
logging.basicConfig(level=logging.DEBUG)
```

**Check Backend Logs:**
```bash
# Terminal running uvicorn will show API requests
```

**Check Detection Logs:**
```bash
tail -f backend/detection_service.log  # Linux/Mac
Get-Content backend\detection_service.log -Wait  # Windows PowerShell
```

## 📝 API Documentation

Once the backend is running, visit:
- **Interactive Docs**: http://localhost:8000/docs
- **Alternative Docs**: http://localhost:8000/redoc

### Key Endpoints

**Authentication:**
- `POST /login` - Get JWT token

**Cameras:**
- `GET /camera/list` - List all cameras
- `POST /camera/add` - Add new camera
- `DELETE /camera/delete/{id}` - Delete camera

**Detections:**
- `POST /vehicle/store` - Store new detection
- `GET /vehicle/active` - Get active detections
- `GET /vehicle/by-camera/{id}` - Get detections by camera
- `DELETE /vehicle/delete-all` - Clear all detections

**Upload:**
- `POST /upload/video` - Upload video and start detection

**Live Feed:**
- `GET /live-feed/{camera_id}` - Access live MJPEG stream with AI overlays

## 🚀 Advanced Features

### GPU Acceleration

The system automatically detects and uses NVIDIA GPUs with CUDA:

**Check GPU Status:**
```python
import torch
print(torch.cuda.is_available())  # Should return True
```

**Expected Speedup:**
- CPU: ~5-10 FPS
- GPU (CUDA): ~20-60 FPS (depending on GPU)

### Custom Models

**Add Custom YOLO Model:**
1. Place model in `ai_engine/`
2. Update `detection_service.py` line ~84:
   ```python
   model_path = 'your_custom_model.pt'
   ```

**Train Custom Plate Model:**
- Use Roboflow or Ultralytics for training
- Export as YOLOv8 format
- Place in `ai_engine/models/license_plate.pt`

## 📄 License

This project is for educational and commercial use.

## 🤝 Support

For issues or questions:
1. Check the Troubleshooting section
2. Review logs in `backend/detection_service.log`
3. Check API docs at http://localhost:8000/docs

## 🎉 Credits

**Technologies Used:**
- **YOLOv8** by Ultralytics
- **EasyOCR** by JaidedAI
- **FastAPI** by Sebastián Ramírez
- **React** by Meta
- **PyTorch** by Meta AI

---

**Version**: 2.0 (Advanced Tracking & ANPR)  
**Last Updated**: January 2026

# License Plate Detection Model Setup

## Quick Start

The ANPR system works in two modes:

1. **With Specialized Plate Model** (Recommended) - Higher accuracy
2. **OCR-Only Mode** (Fallback) - Works but lower accuracy

## Option 1: Automatic Download (Try First)

Run the download script:

```bash
python ai_engine/download_plate_model.py
```

If this fails (GitHub/Kaggle access issues), use Option 2.

## Option 2: Manual Download

### Step 1: Download a Pre-trained Model

Choose ONE of these sources:

**Option A - Kaggle (Recommended)**
1. Visit: https://www.kaggle.com/datasets/andrewmvd/car-plate-detection
2. Download the dataset
3. Extract and find the `best.pt` file

**Option B - GitHub**
1. Visit: https://github.com/computervisioneng/automatic-number-plate-recognition-python-yolov8
2. Navigate to the `models/` folder
3. Download `license_plate_detector.pt`

**Option C - Alternative GitHub**
1. Visit: https://github.com/SiddharthUchil/ANPR-YOLOv8
2. Download the `best.pt` file from the repository

### Step 2: Install the Model

Rename the downloaded file to `license_plate.pt` and place it here:

```
c:/projects/nozz/ai_engine/models/license_plate.pt
```

### Step 3: Restart Detection

1. Stop any running detection processes
2. Re-upload your video through the web interface
3. The system will automatically use the new model

## Verification

Check the logs (`backend/detection_service.log`) for:

```
✓ License Plate model loaded: Local Model
```

If you see this, the specialized model is active!

If you see:
```
⚠ No specialized plate model - using OCR-only mode
```

Then the system is using OCR-only mode (still works, but lower accuracy).

## Troubleshooting

**Model not loading?**
- Ensure the file is named exactly `license_plate.pt`
- Check that it's in the correct directory: `ai_engine/models/`
- Verify the file size is reasonable (should be 5-50 MB)

**Still not working?**
- The system will work in OCR-only mode
- License plates will still be detected, just with lower accuracy
- Check logs for specific error messages

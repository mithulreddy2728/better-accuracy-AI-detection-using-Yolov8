# 🪟 Windows Docker Deployment Guide
## YOLOv8 AI Detection & Vehicle Monitoring System

> Step-by-step guide for deploying on **Windows using Docker Desktop** and **PowerShell**.

---

## Table of Contents

1. [Install Prerequisites](#1-install-prerequisites)
2. [Verify Docker is Running](#2-verify-docker-is-running)
3. [Prepare Model Files](#3-prepare-model-files)
4. [Set Up Environment Variables](#4-set-up-environment-variables)
5. [Build Docker Images](#5-build-docker-images)
6. [Start All Services](#6-start-all-services)
7. [Create Admin User](#7-create-admin-user)
8. [Open the App in Browser](#8-open-the-app-in-browser)
9. [Initialize Git & Push to GitHub](#9-initialize-git--push-to-github)
10. [Stop / Restart Services](#10-stop--restart-services)
11. [Troubleshooting on Windows](#11-troubleshooting-on-windows)

---

## 1. Install Prerequisites

### Docker Desktop for Windows

1. Download from: **https://www.docker.com/products/docker-desktop**
2. Run the installer (`Docker Desktop Installer.exe`)
3. During install, **enable WSL 2** when prompted (recommended over Hyper-V)
4. Restart your PC after install
5. Launch **Docker Desktop** from the Start Menu — wait for it to show **"Engine running"**

### Python (for downloading model files)

Download from **https://www.python.org/downloads/** — install Python 3.11+  
✅ Check **"Add Python to PATH"** during install

---

## 2. Verify Docker is Running

Open **PowerShell** (search "PowerShell" in Start Menu) and run:

```powershell
docker --version
docker compose version
```

Expected output:
```
Docker version 26.x.x, build ...
Docker Compose version v2.x.x
```

> ⚠️ If you get `'docker' is not recognized`, Docker Desktop is not running. Open it from the Start Menu and wait for the whale icon in the taskbar.

---

## 3. Prepare Model Files

The AI model files are large and not included in the project. You need to download them **before** building.

### Open PowerShell in the Project Folder

Right-click the project folder in File Explorer → **"Open in Terminal"** (or **"Open PowerShell window here"**)

Or navigate manually in PowerShell:

```powershell
cd "C:\Users\RIYAZ\Desktop\Projects\better-accuracy-AI-detection-using-Yolov8-main"
```

### Install Ultralytics (one-time, to download models)

```powershell
pip install ultralytics
```

### Download the Main YOLOv8x Model

```powershell
python -c "from ultralytics import YOLO; YOLO('yolov8x.pt')"
```

This downloads `yolov8x.pt` (~130 MB) to your current folder.  
Then copy it to the backend folder:

```powershell
Copy-Item "yolov8x.pt" "backend\yolov8x.pt"
```

### Download the License Plate Model

```powershell
python -c "from ultralytics import YOLO; model = YOLO('keremberke/yolov8n-license-plate-detection'); print('Downloaded')"
```

Find the downloaded `.pt` file (usually in `C:\Users\RIYAZ\AppData\Roaming\Ultralytics\` or similar) and copy it:

```powershell
# Create the models directory if it doesn't exist
New-Item -ItemType Directory -Force -Path "ai_engine\models"

# Copy the model (adjust source path if needed)
# The file may be named differently — check Ultralytics cache folder
# Common location:
Copy-Item "$env:USERPROFILE\AppData\Roaming\Ultralytics\*.pt" "ai_engine\models\license_plate.pt"
```

> 💡 **Alternative**: If you already have a `license_plate.pt` file, just copy it manually to `ai_engine\models\license_plate.pt`.

---

## 4. Set Up Environment Variables

In PowerShell, run these commands to create your `.env` file:

```powershell
# Generate a random secret key
$secret = -join ((65..90) + (97..122) + (48..57) | Get-Random -Count 48 | ForEach-Object {[char]$_})

# Create the .env file
@"
SECRET_KEY=$secret
DATABASE_URL=sqlite:///./nozzle_detection.db
CORS_ORIGINS=http://localhost,http://localhost:80,http://localhost:3000
AI_API_BASE_URL=http://backend:8000
DETECTION_INTERVAL=5
API_HOST=0.0.0.0
API_PORT=8000
"@ | Out-File -FilePath ".env" -Encoding UTF8

Write-Host "✅ .env file created successfully"
```

Verify it was created:

```powershell
Get-Content .env
```

---

## 5. Build Docker Images

> ⏱ This step takes **5–20 minutes** on first run (downloads PyTorch, PaddleOCR, etc.)

```powershell
docker compose build
```

You will see output like:
```
[+] Building 234.5s (42/42) FINISHED
 => [backend] installing requirements...
 => [frontend] npm run build...
 => [ai-engine] pip install...
```

If there are any errors, scroll up to find them — see [Troubleshooting](#11-troubleshooting-on-windows).

---

## 6. Start All Services

```powershell
docker compose up -d
```

Check that all containers are running:

```powershell
docker compose ps
```

Expected output:
```
NAME               IMAGE              STATUS          PORTS
...-backend-1      ...-backend        Up              0.0.0.0:8000->8000/tcp
...-frontend-1     ...-frontend       Up              0.0.0.0:80->80/tcp
...-ai-engine-1    ...-ai-engine      Up
```

All three services should show **Up**.

Watch the logs to make sure nothing is crashing:

```powershell
docker compose logs -f
```

Press `Ctrl+C` to stop watching logs (services keep running).

---

## 7. Create Admin User

The system requires an admin account to log in. Run this in PowerShell:

```powershell
Invoke-RestMethod -Uri "http://localhost:8000/register" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"username": "admin", "password": "Admin@1234", "role": "admin"}'
```

Expected response:
```json
{
  "access_token": "eyJhbGciOiJIUzI1...",
  "token_type": "bearer"
}
```

> Or open **http://localhost:8000/docs** in your browser and use the Swagger UI to register (click `/register` → Try it out).

---

## 8. Open the App in Browser

| URL | What you'll see |
|-----|----------------|
| **http://localhost** | 🖥 React frontend (login page) |
| **http://localhost:8000/docs** | 📖 FastAPI Swagger API docs |
| **http://localhost:8000** | ✅ API health check JSON |

Log in with the username and password you just created.

---

## 9. Initialize Git & Push to GitHub

Since the project has no `.git` folder yet, here's how to set it up:

### Step 1 – Initialize the repo

```powershell
git init
git add .
git commit -m "fix: resolve all deployment issues + add Docker Windows deploy guide"
```

### Step 2 – Create a GitHub repo

1. Go to **https://github.com/new**
2. Name your repo (e.g., `yolov8-ai-detection`)
3. Leave it **empty** (don't add README or .gitignore — we have those)
4. Click **Create repository**

### Step 3 – Link and push

```powershell
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

> Replace `YOUR_USERNAME` and `YOUR_REPO_NAME` with your actual GitHub username and repo name.

---

## 10. Stop / Restart Services

```powershell
# Stop all services (data is preserved)
docker compose down

# Start again
docker compose up -d

# Restart a single service (e.g., after code change)
docker compose restart backend

# Rebuild and restart a single service
docker compose up -d --build backend

# See logs for one service
docker compose logs -f backend

# Stop everything and delete all data (⚠ destructive)
docker compose down -v
```

---

## 11. Troubleshooting on Windows

### ❌ `docker: command not found` or `'docker' is not recognized`

- Open **Docker Desktop** from Start Menu
- Wait for the status to show **"Engine running"** (whale icon in system tray)
- Restart PowerShell and try again

### ❌ Build fails with `pip install` errors (PaddleOCR / PyTorch)

```powershell
# Clean build cache and retry
docker compose build --no-cache
```

> PaddleOCR and PyTorch are large packages. Make sure you have a stable internet connection.

### ❌ Port 80 already in use

Windows may have IIS or another service using port 80. Either:

**Option A** — Stop IIS:
```powershell
net stop w3svc
```

**Option B** — Change the port in `docker-compose.yml`:
```yaml
# Change port 80 to 8080
ports:
  - "8080:80"
```
Then access the app at **http://localhost:8080**

### ❌ Frontend shows blank page

```powershell
# Check frontend container logs
docker compose logs frontend
```

If you see a build error, try:
```powershell
docker compose build --no-cache frontend
docker compose up -d frontend
```

### ❌ AI Engine crashes immediately

```powershell
docker compose logs ai-engine
```

Common cause: **backend not ready yet**. The AI engine waits up to 100 seconds for the backend. If it's still failing:

```powershell
# Restart just the AI engine
docker compose restart ai-engine
```

### ❌ CORS error in browser console

Make sure your `.env` has:
```
CORS_ORIGINS=http://localhost,http://localhost:80
```

Then rebuild the backend:
```powershell
docker compose up -d --build backend
```

### ❌ Login fails (401 error)

You may not have created the admin user yet. Go to **Step 7** and run the registration command.

### ❌ Docker Desktop WSL 2 error on startup

Run in PowerShell **as Administrator**:
```powershell
wsl --update
wsl --set-default-version 2
```
Then restart Docker Desktop.

---

## Quick Reference Card

```powershell
# Navigate to project
cd "C:\Users\RIYAZ\Desktop\Projects\better-accuracy-AI-detection-using-Yolov8-main"

# Build everything
docker compose build

# Start everything
docker compose up -d

# Check status
docker compose ps

# Watch logs
docker compose logs -f

# Stop everything
docker compose down

# Open app
Start-Process "http://localhost"

# Open API docs
Start-Process "http://localhost:8000/docs"
```

---

> 📋 For cloud/VPS deployment (AWS, DigitalOcean, etc.), see the full [DEPLOY.md](./DEPLOY.md)

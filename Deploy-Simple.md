# ⚡ Quick Deploy Guide (Windows PowerShell)

## Prerequisites
Before starting, ensure the following are installed on the target laptop:
1. **Docker Desktop** (installed, running, and set to Linux containers mode)
2. **Python 3.8+** (with `pip` added to your system's PATH)

Follow these exact steps in **PowerShell** to deploy the application freshly:

---

### Step 1: Navigate to the project directory
```powershell
# Change this path to where you cloned/extracted the project on your laptop
cd "C:\path\to\better-accuracy-AI-detection-using-Yolov8-main"
```

### Step 2: Download and prepare model files
```powershell
# Install downloader dependencies
pip install requests ultralytics

# Download the main yolov8x model
python -c "from ultralytics import YOLO; YOLO('yolov8x.pt')"

# Copy the model to the backend directory
Copy-Item "yolov8x.pt" "backend\yolov8x.pt"

# Automatically download the license plate detection model weights
python ai_engine/download_plate_model.py
```

### Step 3: Setup environment configuration (.env)
```powershell
$secret = -join ((65..90)+(97..122)+(48..57) | Get-Random -Count 48 | ForEach-Object {[char]$_})
@"
SECRET_KEY=$secret
DATABASE_URL=sqlite:///./nozzle_detection.db
CORS_ORIGINS=http://localhost,http://localhost:80,http://localhost:3000
AI_API_BASE_URL=http://backend:8000
DETECTION_INTERVAL=5
API_HOST=0.0.0.0
API_PORT=8000
"@ | Out-File -FilePath ".env" -Encoding UTF8
```

### Step 4: Build and launch containers
```powershell
# Build all backend, frontend, and AI engine images
docker compose build

# Start services in the background
docker compose up -d
```

### Step 5: Register the Admin User
Wait 10 seconds for the database schema to initialize, then run:
```powershell
Invoke-RestMethod -Uri "http://localhost:8000/register" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"username":"admin","password":"Admin@1234","role":"admin"}'
```

### Step 6: Launch browser
```powershell
Start-Process "http://localhost"
```

---

*   **Frontend Access**: [http://localhost](http://localhost)
*   **Backend API Documentation**: [http://localhost:8000/docs](http://localhost:8000/docs)
*   **Admin Username**: `admin`
*   **Admin Password**: `Admin@1234`

---

## 🌐 Customizing Domain / Hostname (Optional)

If you want to access the app using a custom name (like `http://mycustomname.com`) instead of `localhost`, follow these steps:

### 1. Update CORS in `.env`
Open your `.env` file and add the domain to `CORS_ORIGINS`:
```env
CORS_ORIGINS=http://mycustomname.com,http://localhost,http://localhost:80
```

### 2. Configure Windows Hosts File (Local Routing)
1. Open **Notepad** (search in Start Menu) by right-clicking it and choosing **Run as Administrator**.
2. Open the hosts file: `C:\Windows\System32\drivers\etc\hosts`
3. Append this line at the very bottom:
   ```text
   127.0.0.1  mycustomname.com
   ```
4. Save and close Notepad.

### 3. Restart Docker Services
```powershell
docker compose up -d --force-recreate
```

You can now open **`http://mycustomname.com`** in your browser.

---

## 🌐 Sharing Globally / Remote Access (using ngrok)

If you want someone in a completely different location (another city/network) to access your app:

### 1. Download and Authenticate ngrok
1. Go to **[https://ngrok.com](https://ngrok.com)**, create a free account, and download the Windows version.
2. Open PowerShell and run the command to authenticate your account (copy this command from your ngrok dashboard):
   ```powershell
   ngrok config add-authtoken YOUR_NGROK_AUTHTOKEN
   ```

### 2. Expose Port 80 (Nginx Frontend)

You can run ngrok in the foreground (standard terminal window) or in the background (hidden window) so that it keeps running even if you close your terminal or code editor (e.g., VS Code/Cursor).

#### Option A: Run in Background (Recommended)
This runs ngrok as a hidden process that persists even after closing your terminal or editor:
```powershell
# Start ngrok in a hidden window
Start-Process ngrok -ArgumentList "http 80" -WindowStyle Hidden
```

To find your **Forwarding URL** or manage the background process:
```powershell
# 1. Retrieve the active forwarding URL
(Invoke-RestMethod -Uri "http://127.0.0.1:4040/api/tunnels").tunnels.public_url

# 2. Check if ngrok is currently running
Get-Process ngrok

# 3. Stop the background ngrok process when done
Stop-Process -Name ngrok -Force
```
You can also view the active tunnel, configuration, and logs by opening the local ngrok web dashboard: **[http://127.0.0.1:4040](http://127.0.0.1:4040)**.

#### Option B: Run in Foreground (Standard)
Run this command to keep ngrok running in your active terminal:
```powershell
ngrok http 80
```
> ⚠️ **Note**: Closing this terminal window or your code editor while ngrok is running in the foreground will terminate the tunnel.

---

### 💡 Lifecycle & Background Persistence Notice
*   **Docker Containers**: Because you launched the containers using the `-d` detached flag (`docker compose up -d`), they run as background services managed by the Docker Desktop VM. Closing your terminal or editor **will not stop** the containers.
*   **Ngrok (Hidden)**: If you ran ngrok using the `Start-Process ... -WindowStyle Hidden` command (Option A), the process is detached from your shell session. Closing your terminal or editor **will not stop** the tunnel.
*   **To fully stop everything**, you must run:
    ```powershell
    # Stop the Docker containers
    docker compose down

    # Stop the ngrok background process
    Stop-Process -Name ngrok -Force
    ```

---

### 3. Add the ngrok URL to CORS
Open your **`docker-compose.yml`** file, look for the `CORS_ORIGINS` line under the `backend` service, and append your ngrok URL (separated by a comma, no spaces):
```yaml
      - CORS_ORIGINS=http://localhost,http://localhost:80,http://localhost:3000,https://YOUR-SUBDOMAIN.ngrok-free.app
```

### 4. Restart Docker Containers
Apply the CORS settings by restarting:
```powershell
docker compose up -d --force-recreate
```

Your remote user can now access the app globally by visiting the copied ngrok URL!

---

## 🎥 Monitoring with your Laptop's Built-in Webcam

Because Docker runs in an isolated virtual machine, it cannot access your physical laptop camera (Device 0) directly. To stream your local webcam to the AI detection engine:

### 1. Run the Webcam Streamer Script (On Host Laptop)
1. Install OpenCV on your host machine:
   ```powershell
   pip install opencv-python
   ```
2. Launch the streamer script from your project root:
   ```powershell
   python ai_engine/share_webcam.py
   ```
This will start a local MJPEG server at `http://localhost:8085/stream`.

### 2. Register and Monitor the Webcam in the Web Dashboard
1. Log in to the web interface (`http://localhost` or your ngrok URL).
2. Go to the **Cameras** page in the left menu.
3. Click **Add Camera**.
4. Configure the form:
   * **Type**: `URL`
   * **Source**: `http://host.docker.internal:8085/stream`
5. Click **Save** and start monitoring! The AI engine will connect to your camera stream and begin detecting in real-time.




import subprocess
import logging
from typing import Dict, Optional

# Global dictionary to track processes by camera_id
# camera_id -> {"process": subprocess.Popen, "files": [file_objects]}
_active_processes: Dict[int, dict] = {}

def start_process(camera_id: int, command: list, **kwargs) -> subprocess.Popen:
    """
    Start a new subprocess for a camera and track it.
    If a process already exists for this camera, it will be stopped first.
    """
    stop_process(camera_id)
    
    try:
        # Extract file objects from kwargs to track them
        files_to_track = []
        for key in ['stdout', 'stderr']:
            val = kwargs.get(key)
            if val and hasattr(val, 'close'):
                files_to_track.append(val)
                
        process = subprocess.Popen(command, **kwargs)
        _active_processes[camera_id] = {
            "process": process,
            "files": files_to_track
        }
        logging.info(f"Started detection process for camera {camera_id} (PID: {process.pid})")
        return process
    except Exception as e:
        logging.error(f"Failed to start process for camera {camera_id}: {e}")
        # Close files if we opened them but process failed to start
        for f in files_to_track:
            try:
                f.close()
            except:
                pass
        raise

def stop_process(camera_id: int):
    """
    Stop the subprocess associated with a camera_id.
    """
    if camera_id in _active_processes:
        data = _active_processes[camera_id]
        process = data["process"]
        try:
            if process.poll() is None:  # Process is still running
                logging.info(f"Stopping detection process for camera {camera_id} (PID: {process.pid})")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            
            # Close file handles to release file locks (important for Windows)
            for f in data.get("files", []):
                try:
                    f.close()
                except:
                    pass
                    
            del _active_processes[camera_id]
        except Exception as e:
            logging.error(f"Error stopping process for camera {camera_id}: {e}")

def cleanup_orphans():
    """
    Kill any detection_service.py processes that might be running 
    from previous backend instances.
    """
    import os
    import sys
    import subprocess
    
    print("Checking for orphan detection processes...")
    try:
        if sys.platform == "win32":
            # Use PowerShell to find and kill processes with 'detection_service.py' in the command line
            # This is more reliable on modern Windows than wmic
            ps_cmd = (
                "powershell -Command \"Get-CimInstance Win32_Process "
                "-Filter 'Name = ''python.exe''' | "
                "Where-Object { $_.CommandLine -like '*detection_service.py*' } | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }\""
            )
            subprocess.run(ps_cmd, shell=True, capture_output=True)
            print("Successfully checked for and cleaned orphan processes.")
        else:
            # Unix/Linux: Use pgrep/pkill
            subprocess.run(['pkill', '-f', 'detection_service.py'], capture_output=True)
            
    except Exception as e:
        print(f"Error during orphan cleanup: {e}")

def get_process(camera_id: int) -> Optional[subprocess.Popen]:
    """
    Check if a process is running for a camera and return its handle.
    """
    if camera_id in _active_processes:
        data = _active_processes[camera_id]
        process = data["process"]
        if process.poll() is not None:  # Process has terminated
            # Close files and cleanup
            for f in data.get("files", []):
                try:
                    f.close()
                except:
                    pass
            del _active_processes[camera_id]
            return None
        return process
    return None

def stop_all():
    """
    Stop all active detection processes.
    """
    camera_ids = list(_active_processes.keys())
    for cid in camera_ids:
        stop_process(cid)

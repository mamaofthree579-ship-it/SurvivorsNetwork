import subprocess
import threading
import sys
import time
import os

def start_backend_engine():
    """Launches your verify.py service node silently in the background"""
    # Locates the local path dynamically inside the standalone compiled package environment
    base_path = os.path.dirname(os.path.abspath(__file__))
    verify_script = os.path.join(base_path, "verify.py")
    
    # Fire up the backend engine on local port 8001 without opening an annoying console window
    subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "verify:app", "--host", "127.0.0.1", "--port", "8001", "--log-level", "warning"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

def start_frontend_dashboard():
    """Spins up the Streamlit interface layer natively inside the app wrap"""
    base_path = os.path.dirname(os.path.abspath(__file__))
    app_script = os.path.join(base_path, "app.py")
    
    # Forces Streamlit to run locally, bypassing corporate telemetry options
    subprocess.run([
        sys.executable, "-m", "streamlit", "run", app_script,
        "--server.headless=true",
        "--server.port=8501",
        "--browser.gatherUsageStats=false"
    ])

if __name__ == "__main__":
    # 1. Fire up the data verifier node service on port 8001
    backend_thread = threading.Thread(target=start_backend_engine, daemon=True)
    backend_thread.start()
    
    # 2. Give the background port a moment to open up sockets safely
    time.sleep(2)
    
    # 3. Initialize the graphic user space portal dashboard loop
    start_frontend_dashboard()

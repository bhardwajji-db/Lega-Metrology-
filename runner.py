import os
import sys
import time
import socket
import subprocess
import webbrowser
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

def log(msg: str = ""):
    print(msg, flush=True)

def get_lan_ip() -> str:
    """Detect active local network IP address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip

def kill_ports(ports=(5173, 8000)):
    """Clean up any existing processes on specified ports (Windows)."""
    if os.name == 'nt':
        port_list = ','.join(str(p) for p in ports)
        cmd = f"powershell -NoProfile -Command \"(Get-NetTCPConnection -LocalPort {port_list} -State Listen -ErrorAction SilentlyContinue).OwningProcess | Select-Object -Unique | ForEach-Object {{ Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }}\""
        subprocess.run(cmd, shell=True, capture_output=True)

def check_and_prompt_firewall():
    """Checks if Windows Firewall rule exists for MetrCheck. If not, offers guidance."""
    if os.name == 'nt':
        try:
            check_cmd = "powershell -NoProfile -Command \"(Get-NetFirewallRule -DisplayName 'MetrCheck AI (5173, 8000)' -ErrorAction SilentlyContinue).DisplayName\""
            res = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
            if "MetrCheck" not in res.stdout:
                log("[*] Note: If your phone cannot connect on local Wi-Fi, run allow_firewall.bat as Admin once.")
        except Exception:
            pass
def wait_for_service(url: str, total_timeout: float = 30.0, req_timeout: float = 8.0) -> bool:
    """Poll a service URL until HTTP 200/304 is returned or timeout expires."""
    start_time = time.time()
    while time.time() - start_time < total_timeout:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MetrCheck-HealthCheck"})
            with urllib.request.urlopen(req, timeout=req_timeout) as resp:
                if resp.status in (200, 304):
                    return True
        except Exception:
            pass
        time.sleep(0.8)
    return False

def print_qr(url: str):
    """Print ASCII QR Code to terminal for instant mobile camera scanning."""
    try:
        import qrcode
        qr = qrcode.QRCode(box_size=1, border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except Exception:
        pass

def main():
    log("=" * 64)
    log("     MetrCheck AI - Automated Launch & Verification System")
    log("================================================================")
    log()

    # 1. Detect LAN IP & Check Firewall
    lan_ip = get_lan_ip()
    universal_url = f"http://{lan_ip}:5173"
    api_docs_url = f"http://{lan_ip}:8000/docs"
    health_url = "http://127.0.0.1:8000/api/health"
    frontend_check_url = "http://127.0.0.1:5173"

    log(f"[*] Detected Local Network IP: {lan_ip}")
    check_and_prompt_firewall()

    log("[*] Terminating previous instances on ports 5173 and 8000...")
    kill_ports((5173, 8000))
    time.sleep(1)

    # 2. Start Backend
    log("[*] Starting FastAPI Backend (0.0.0.0:8000)...")
    python_exe = sys.executable
    backend_env = os.environ.copy()
    
    backend_log_file = open(ROOT_DIR / "backend.log", "w", encoding="utf-8")
    backend_proc = subprocess.Popen(
        [
            python_exe, "-m", "uvicorn", "main:app",
            "--host", "0.0.0.0",
            "--port", "8000"
        ],
        cwd=str(BACKEND_DIR),
        env=backend_env,
        stdout=backend_log_file,
        stderr=subprocess.STDOUT
    )

    # 3. Start Frontend
    log("[*] Starting Vite React Frontend (0.0.0.0:5173)...")
    frontend_log_file = open(ROOT_DIR / "frontend.log", "w", encoding="utf-8")
    frontend_proc = subprocess.Popen(
        "npm run dev",
        cwd=str(FRONTEND_DIR),
        shell=True,
        stdout=frontend_log_file,
        stderr=subprocess.STDOUT
    )

    # 4. Automated Health Verification
    log("[*] Running automated health checks on Backend and Frontend...")
    backend_ok = wait_for_service(health_url, total_timeout=30.0, req_timeout=8.0)
    frontend_ok = wait_for_service(frontend_check_url, total_timeout=20.0, req_timeout=4.0)

    log()
    log("=" * 64)
    if backend_ok and frontend_ok:
        log("  [SUCCESS] ALL SERVICES ARE ONLINE AND VERIFIED!")
        log("  Backend Health:  OK (http://127.0.0.1:8000/api/health)")
        log("  Frontend Server: OK (http://127.0.0.1:5173)")
    else:
        status_msg = []
        if not backend_ok: status_msg.append("Backend check timed out")
        if not frontend_ok: status_msg.append("Frontend check timed out")
        log(f"  [WARNING] System started with warnings: {', '.join(status_msg)}")
    log("=" * 64)
    log()
    log("  * SINGLE UNIVERSAL URL (FOR BOTH LAPTOP AND PHONE) *")
    log(f"  --> \033[1;32m{universal_url}\033[0m")
    log()
    log("  Scan this QR Code with your Phone Camera to open instantly:")
    log("-" * 64)
    print_qr(universal_url)
    log("-" * 64)
    log(f"  * Laptop Direct URL:    http://localhost:5173")
    log(f"  * Interactive API Docs: {api_docs_url}")
    log("=" * 64)
    log()
    log("  * INSTRUCTIONS FOR PHONE:")
    log(f"  1. Ensure your phone is connected to the same Wi-Fi or Hotspot.")
    log(f"  2. If the page shows 'Site can't be reached', run allow_firewall.bat as Admin")
    log(f"     to allow Windows Firewall port 5173/8000, or run tunnel.bat for instant HTTPS.")
    log(f"  3. Open your mobile browser and navigate to: {universal_url}")
    log()
    log("  Press Ctrl+C in this terminal anytime to stop both servers.")
    log("=" * 64)

    # 5. Open browser on laptop automatically
    try:
        webbrowser.open(universal_url)
    except Exception:
        pass

    try:
        while True:
            if backend_proc.poll() is not None:
                log("[!] Backend process terminated.")
                break
            if frontend_proc.poll() is not None:
                log("[!] Frontend process terminated.")
                break
            time.sleep(1)
    except KeyboardInterrupt:
        log("\n[*] Stopping MetrCheck AI servers...")
    finally:
        try:
            backend_proc.terminate()
        except Exception:
            pass
        try:
            frontend_proc.terminate()
        except Exception:
            pass
        try:
            backend_log_file.close()
            frontend_log_file.close()
        except Exception:
            pass
        kill_ports((5173, 8000))
        log("[*] Servers stopped cleanly. Goodbye!")

if __name__ == "__main__":
    main()

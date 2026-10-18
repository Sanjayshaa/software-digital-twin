import os
import sys
import socket

# Ensure backend root is on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

def check_port(port=8000):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('127.0.0.1', port)) != 0

if __name__ == "__main__":
    os.chdir(BACKEND_DIR)
    
    port = 8000
    if not check_port(port):
        print(f"WARNING: Port {port} is already in use by another process!")
        print(f"You can kill the existing process with: lsof -ti:{port} | xargs kill -9")
    
    print("=" * 65)
    print(" STARTING SOFTWARE DIGITAL TWIN ENTERPRISE SERVER")
    print("=" * 65)
    print(" Database: Supabase Enterprise Cloud (software-digital-twin)")
    print(" Engine:   PostgreSQL 17.11 (ap-south-1)")
    print(f" Web UI:   http://localhost:{port}/app")
    print(f" Status:   http://localhost:{port}/ready")
    print(f" Docs:     http://localhost:{port}/docs")
    print("=" * 65)

    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)

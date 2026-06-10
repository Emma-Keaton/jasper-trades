#!/usr/bin/env python3
"""
Jasper Trades - Backend Server Starter
Starts the FastAPI backend with uvicorn.
"""

import subprocess
import sys
import os


def main():
    """Start the FastAPI backend server."""
    # Ensure we're in the backend directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    print("=" * 50)
    print("Jasper Trades - Backend Server")
    print("=" * 50)
    print()
    print("Starting uvicorn server...")
    print("URL: http://localhost:8000")
    print("API Docs: http://localhost:8000/docs")
    print()
    print("Press Ctrl+C to stop")
    print("=" * 50)
    print()
    
    # Start the server
    try:
        subprocess.run([
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
            "--reload"
        ], check=True)
    except KeyboardInterrupt:
        print("\n\nServer stopped.")
    except subprocess.CalledProcessError as e:
        print(f"Error: Server exited with code {e.returncode}")
        sys.exit(1)


if __name__ == "__main__":
    main()
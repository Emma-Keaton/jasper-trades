#!/usr/bin/env python3
"""
Jasper Trades - Complete Setup Script

This script installs all dependencies and sets up the project for local development:
- Python backend dependencies (FastAPI, etc.)
- Node.js frontend dependencies
- Kronos forecast service dependencies (CPU-only, 2GB RAM friendly)
- Environment configuration
- Database initialization
- Optional: Start all servers (frontend, backend, kronos)

Usage:
    python setup.py [--dev] [--prod] [--skip-frontend] [--skip-backend] [--skip-kronos] [--start] [--help]

Endpoints after startup:
    Frontend:  http://localhost:3000
    Backend:   http://localhost:8000
    Kronos:    http://localhost:8001
"""

import argparse
import os
import sys
import subprocess
import platform
import shutil
import json
import secrets
import signal
import time
from pathlib import Path
from typing import Optional, List, Tuple

# Colors for output
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_step(msg: str):
    print(f"\n{Colors.BLUE}{Colors.BOLD}>> {msg}{Colors.END}")

def print_success(msg: str):
    print(f"{Colors.GREEN}[OK] {msg}{Colors.END}")

def print_warning(msg: str):
    print(f"{Colors.YELLOW}[WARN] {msg}{Colors.END}")

def print_error(msg: str):
    print(f"{Colors.RED}[ERR] {msg}{Colors.END}")

def print_info(msg: str):
    print(f"{Colors.CYAN}[INFO] {msg}{Colors.END}")

# Global list of running server processes for cleanup
_server_processes: List[subprocess.Popen] = []

def cleanup_servers(signum=None, frame=None):
    """Stop all running server processes on exit or signal."""
    print_info("\nShutting down servers...")
    for proc in _server_processes:
        if proc.poll() is None:
            proc.terminate()
    for proc in _server_processes:
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    print_success("All servers stopped.")
    sys.exit(0)

def run_command(cmd: List[str], cwd: Optional[Path] = None, env: Optional[dict] = None,
                capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    """Run a command and return the result."""
    print_info(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=cwd, env=env, capture_output=capture, text=True)
    if check and result.returncode != 0:
        print_error(f"Command failed: {' '.join(cmd)}")
        if capture:
            print_error(f"stdout: {result.stdout}")
            print_error(f"stderr: {result.stderr}")
        sys.exit(1)
    return result

def start_background(cmd: List[str], cwd: Optional[Path] = None, env: Optional[dict] = None,
                     log_file: Optional[str] = None) -> subprocess.Popen:
    """Start a command in the background and track it for cleanup."""
    print_info(f"Starting (background): {' '.join(cmd)}")
    log_fh = open(log_file, "w") if log_file else None
    proc = subprocess.Popen(
        cmd, cwd=cwd, env=env,
        stdout=log_fh, stderr=log_fh or subprocess.PIPE,
        text=True,
    )
    _server_processes.append(proc)
    return proc

def check_command_exists(cmd: str) -> bool:
    """Check if a command exists in PATH."""
    return shutil.which(cmd) is not None

def get_python_version() -> Tuple[int, int]:
    """Get Python major and minor version."""
    return sys.version_info.major, sys.version_info.minor

def check_python_version() -> bool:
    """Check if Python version is compatible (3.11+)."""
    major, minor = get_python_version()
    if major < 3 or (major == 3 and minor < 11):
        print_error(f"Python 3.11+ required, found {major}.{minor}")
        return False
    print_success(f"Python {major}.{minor} detected")
    return True

def check_node_version() -> bool:
    """Check if Node.js is installed."""
    if not check_command_exists("node"):
        print_error("Node.js not found. Please install Node.js 20+ from https://nodejs.org/")
        return False
    result = run_command(["node", "--version"], capture=True, check=False)
    if result.returncode == 0:
        print_success(f"Node.js {result.stdout.strip()} detected")
        return True
    return False

def check_npm_version() -> bool:
    """Check if npm is installed."""
    if not check_command_exists("npm"):
        print_error("npm not found. Please install Node.js (includes npm) from https://nodejs.org/")
        return False
    result = run_command(["npm", "--version"], capture=True, check=False)
    if result.returncode == 0:
        print_success(f"npm {result.stdout.strip()} detected")
        return True
    return False

def check_modal_cli() -> bool:
    """Check if Modal CLI is installed (needed for cloud deployment)."""
    if not check_command_exists("modal"):
        print_warning("Modal CLI not found. Cloud deployment will be unavailable.")
        print_info("Install with: pip install modal")
        return False
    return True
def create_venv(backend_dir: Path) -> Path:
    """Create virtual environment if it doesn't exist."""
    venv_dir = backend_dir / ".venv"
    if venv_dir.exists():
        print_info("Virtual environment already exists")
        return venv_dir
    print_step("Creating Python virtual environment...")
    run_command([sys.executable, "-m", "venv", str(venv_dir)])
    print_success("Virtual environment created")
    return venv_dir

def get_venv_python(venv_dir: Path) -> Path:
    """Get the Python executable from the virtual environment."""
    if platform.system() == "Windows":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python"

def get_venv_pip(venv_dir: Path) -> Path:
    """Get the pip executable from the virtual environment."""
    if platform.system() == "Windows":
        return venv_dir / "Scripts" / "pip.exe"
    return venv_dir / "bin" / "pip"

def install_python_deps(venv_dir: Path, backend_dir: Path, install_kronos: bool = True):
    """Install Python dependencies."""
    pip = get_venv_pip(venv_dir)
    python = get_venv_python(venv_dir)

    print_step("Upgrading pip...")
    # Use python -m pip on Windows to avoid issues
    if platform.system() == "Windows":
        run_command([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    else:
        run_command([str(pip), "install", "--upgrade", "pip"])

    print_step("Installing Python dependencies from requirements.txt...")
    req_file = backend_dir / "requirements.txt"
    run_command([str(pip), "install", "-r", str(req_file)])

    if install_kronos:
        print_step("Installing Kronos local model dependencies...")
        run_command([
            str(pip), "install",
            "torch", "torchvision", "torchaudio",
            "--index-url", "https://download.pytorch.org/whl/cpu"
        ])
        run_command([str(pip), "install", "huggingface_hub", "safetensors"])
        print_success("Kronos dependencies installed")

    print_success("All Python dependencies installed")

def install_frontend_deps(frontend_dir: Path):
    """Set up environment files from examples."""
    print_step("Setting up environment files...")

    # Root .env
    root_env_example = root_dir / ".env.example"
    root_env = root_dir / ".env"
    if root_env_example.exists() and not root_env.exists():
        shutil.copy(root_env_example, root_env)
        print_success(f"Created {root_env}")

    # Backend .env
    backend_env_example = backend_dir / ".env.example"
    backend_env = backend_dir / ".env"
    if backend_env_example.exists() and not backend_env.exists():
        shutil.copy(backend_env_example, backend_env)
        print_success(f"Created {backend_env}")

    # Frontend .env
    frontend_env_example = frontend_dir / ".env.example"
    frontend_env = frontend_dir / ".env"
    if frontend_env_example.exists() and not frontend_env.exists():
        shutil.copy(frontend_env_example, frontend_env)
        print_success(f"Created {frontend_env}")

    # Generate secret keys
    print_step("Generating secret keys...")

    env_content = backend_env.read_text()

    if "SECRET_KEY=" in env_content and 'SECRET_KEY=""' in env_content:
        secret_key = secrets.token_urlsafe(32)
        env_content = env_content.replace('SECRET_KEY=""', f'SECRET_KEY="{secret_key}"')
        print_success("Generated SECRET_KEY")

    if "API_AUTH_KEY=" in env_content and 'API_AUTH_KEY=""' in env_content:
        api_auth_key = "jasper_" + secrets.token_urlsafe(16)
        env_content = env_content.replace('API_AUTH_KEY=""', f'API_AUTH_KEY="{api_auth_key}"')
        print_success("Generated API_AUTH_KEY")

    if "CTRADER_ENCRYPTION_KEY=" in env_content and 'CTRADER_ENCRYPTION_KEY=""' in env_content:
        from cryptography.fernet import Fernet
        encryption_key = Fernet.generate_key().decode()
        env_content = env_content.replace('CTRADER_ENCRYPTION_KEY=""', f'CTRADER_ENCRYPTION_KEY="{encryption_key}"')
        print_success("Generated CTRADER_ENCRYPTION_KEY")

    backend_env.write_text(env_content)
    print_success("Environment files configured")

def init_database(venv_dir: Path, backend_dir: Path):
    """Initialize the database."""
    python = get_venv_python(venv_dir)
    print_step("Initializing database...")
    init_script = backend_dir / "start_server.py"
    if init_script.exists():
        result = run_command([str(python), str(init_script)], cwd=backend_dir, check=False)
        if result.returncode == 0:
            print_success("Database initialized")
        else:
            print_warning("Database initialization had issues (may be expected on first run)")
def print_summary(args):
    """Print summary of what was set up and how to run."""
    print(f"\n{Colors.BOLD}{Colors.GREEN}{'='*60}")
    print(f"  Jasper Trades Setup Complete!")
    print(f"{'='*60}{Colors.END}\n")

    print(f"{Colors.BOLD}Next Steps:{Colors.END}\n")

    print(f"{Colors.CYAN}1. Configure your API keys:{Colors.END}")
    print(f"   Edit E:\\Projects\\jasper-trades\\.env")
    print(f"   Edit E:\\Projects\\jasper-trades\\backend\\.env")
    print(f"   Required: GROQ_API_KEY, TELEGRAM_BOT_TOKEN")
    print(f"   Optional: CTRADER_*, CCXT_EXCHANGES, KRONOS_SERVICE_URL\n")

    print(f"{Colors.CYAN}2. Start the backend:{Colors.END}")
    print(f"   cd E:\\Projects\\jasper-trades\\backend")
    print(f"   .venv\\Scripts\\activate   # Windows")
    print(f"   python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000\n")

    print(f"{Colors.CYAN}3. Start the frontend (in a new terminal):{Colors.END}")
    print(f"   cd E:\\Projects\\jasper-trades\\frontend")
    print(f"   npm run dev\n")

    print(f"{Colors.CYAN}4. Access the application:{Colors.END}")
    print(f"   Frontend: http://localhost:3000")
    print(f"   Backend API: http://localhost:8000")
    print(f"   API Docs: http://localhost:8000/docs (dev only)\n")

    if args.dev:
        print(f"{Colors.YELLOW}Development mode: Enabled{Colors.END}")
    if args.skip_kronos:
        print(f"{Colors.YELLOW}Kronos local model: Skipped (using fallback forecaster){Colors.END}")
    else:
        print(f"{Colors.YELLOW}Kronos local model: Installed (PyTorch CPU){Colors.END}")

def main():
    parser = argparse.ArgumentParser(description="Jasper Trades Setup Script")
    parser.add_argument("--dev", action="store_true", help="Development mode (default)")
    parser.add_argument("--prod", action="store_true", help="Production mode (build frontend)")
    parser.add_argument("--skip-frontend", action="store_true", help="Skip frontend setup")
    parser.add_argument("--skip-backend", action="store_true", help="Skip backend setup")
    parser.add_argument("--skip-kronos", action="store_true", help="Skip Kronos local model installation")
    parser.add_argument("--skip-tests", action="store_true", help="Skip running tests")
    parser.add_argument("--only-deps", action="store_true", help="Only install dependencies")
    parser.add_argument("--start", action="store_true", help="Start all servers after setup")
    args = parser.parse_args()

    root_dir = Path(__file__).parent.resolve()
    backend_dir = root_dir / "backend"
    frontend_dir = root_dir / "frontend"
    kronos_dir = root_dir / "kronos"

    print(f"{Colors.BOLD}{Colors.BLUE}")
    print("+==============================================================+")
    print("|     Jasper Trades - Complete Setup Script                    |")
    print("|     AI-Powered Trading Platform (Nigeria-First)             |")
    print("+==============================================================+")
    print(f"{Colors.END}\n")

    # Check prerequisites
    print_step("Checking prerequisites...")

    if not check_python_version():
        sys.exit(1)

    if not args.skip_frontend:
        if not check_node_version() or not check_npm_version():
            print_error("Node.js/npm required for frontend. Install from https://nodejs.org/")
            if not args.skip_backend:
                print_info("Continuing with backend only...")
            else:
                sys.exit(1)

    if not args.skip_backend:
        venv_dir = create_venv(backend_dir)
        install_python_deps(venv_dir, backend_dir, install_kronos=not args.skip_kronos)
        setup_env_files(root_dir, backend_dir, frontend_dir)
        init_database(venv_dir, backend_dir)

        if not args.skip_kronos:
            download_kronos_model(venv_dir)

        if not args.skip_tests and not args.only_deps:
            run_tests(venv_dir, backend_dir)

    if not args.skip_frontend:
        install_frontend_deps(frontend_dir)

        if args.prod:
            build_frontend(frontend_dir)

    # Kronos service setup (independent of backend)
    kronos_venv = None
    kronos_python = None
    if not args.skip_kronos and kronos_dir.exists():
        kronos_venv, kronos_python = install_kronos_deps(kronos_dir)
        setup_kronos_env(root_dir, kronos_dir)

    if args.only_deps:
        print_success("Dependencies installed. Run without --only-deps to complete setup.")
        return

    if args.start:
        start_all_servers(
            root_dir, backend_dir, frontend_dir, kronos_dir,
            start_kronos=(not args.skip_kronos and kronos_dir.exists()),
            backend_venv=venv_dir if not args.skip_backend else None,
            kronos_venv=kronos_venv,
            kronos_python=kronos_python,
        )
        return

    print_summary(args)

if __name__ == "__main__":
    main()

def download_kronos_model(venv_dir: Path):
    """Download the Kronos model from Hugging Face."""
    python = get_venv_python(venv_dir)
    print_step("Downloading Kronos model from Hugging Face...")
    script = '''
from huggingface_hub import hf_hub_download
import os

repo_id = "傲慢的狼队/Kronos"
files = ["kronos-mini.safetensors", "kronos-mini-int8.safetensors"]

for filename in files:
    try:
        path = hf_hub_download(repo_id=repo_id, filename=filename)
        print(f"Downloaded {filename} to {path}")
    except Exception as e:
        print(f"Failed to download {filename}: {e}")
'''
    result = run_command([str(python), "-c", script], check=False)
    if result.returncode == 0:
        print_success("Kronos model downloaded")
    else:
        print_warning("Kronos model download had issues (will use fallback forecaster)")

def run_tests(venv_dir: Path, backend_dir: Path):
    """Run the test suite."""
    python = get_venv_python(venv_dir)
    print_step("Running test suite...")
    result = run_command([
        str(python), "-m", "pytest",
        "tests/", "-x", "-q",
        "--ignore=tests/test_agent_integration.py",
        "--ignore=tests/test_boot_budget.py",
        "--ignore=tests/test_boot_lifecycle.py"
    ], cwd=backend_dir, check=False)

    if result.returncode == 0:
        print_success("All tests passed!")
    else:
        print_warning("Some tests failed (check output above)")

def build_frontend(frontend_dir: Path):
    """Build the frontend for production."""
    print_step("Building frontend...")
    run_command(["npm", "run", "build"], cwd=frontend_dir)
    print_success("Frontend built successfully")

def install_frontend_deps(frontend_dir: Path):
    """Install Node.js frontend dependencies."""
    print_step("Installing frontend dependencies...")
    run_command(["npm", "install"], cwd=frontend_dir)
    print_success("Frontend dependencies installed")
    result = run_command(["node", "--version"], capture=True, check=False)
    if result.returncode == 0:
        version = result.stdout.strip()
        print_success(f"Node.js {version} detected")
        return True
    return False

def print_summary(args):
    """Print a summary of what was installed and how to start services."""
    print_step("Setup Complete!")
    print_info("")
    print_info("Next steps:")
    print_info("  1. Review and edit .env files if needed:")
    print_info(f"     - {root_dir}/.env")
    print_info(f"     - {backend_dir}/.env")
    print_info(f"     - {frontend_dir}/.env")
    print_info(f"     - {kronos_dir}/.env (if kronos was not skipped)")
    print_info("")
    print_info("  2. Start all servers:")
    print_info("     python setup.py --start")
    print_info("")
    print_info("  3. Or start individually:")
    print_info("     Backend:  cd backend && python start_server.py")
    print_info("     Frontend: cd frontend && npm run dev")
    print_info("     Kronos:   cd kronos && python start_kronos.py")
    print_info("")
    print_info("Endpoints:")
    print_info("  Frontend:  http://localhost:3000")
    print_info("  Backend:   http://localhost:8000")
    print_info("  Kronos:    http://localhost:8001")

def check_npm_version() -> bool:
    """Check if npm is installed."""
    if not check_command_exists("npm"):
        print_error("npm not found. Please install Node.js (includes npm) from https://nodejs.org/")
        return False
    result = run_command(["npm", "--version"], capture=True, check=False)
    if result.returncode == 0:
        version = result.stdout.strip()
        print_success(f"npm {version} detected")
        return True
    return False

# ---------------------------------------------------------------------------
# Kronos + server startup functions
# ---------------------------------------------------------------------------

def install_kronos_deps(kronos_dir: Path):
    """Install Python dependencies for the Kronos forecast service."""
    print_step("Installing Kronos forecast service dependencies...")
    venv_dir = kronos_dir / ".venv"
    if venv_dir.exists():
        print_info("Kronos virtual environment already exists")
    else:
        run_command([sys.executable, "-m", "venv", str(venv_dir)])
        print_success("Kronos virtual environment created")

    python = get_venv_python(venv_dir)
    run_command([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    run_command([str(python), "-m", "pip", "install", "-r", str(kronos_dir / "requirements.txt")])
    run_command([
        str(python), "-m", "pip", "install", "torch",
        "--index-url", "https://download.pytorch.org/whl/cpu",
    ])
    print_success("Kronos dependencies installed")
    return venv_dir, python

def setup_kronos_env(root_dir: Path, kronos_dir: Path):
    """Set up Kronos environment file (.env) from .env.example."""
    kronos_env = kronos_dir / ".env"
    kronos_example = kronos_dir / ".env.example"

    if kronos_env.exists():
        print_info("Kronos .env already exists, skipping")
        return

    if not kronos_example.exists():
        print_warning("No kronos .env.example found, skipping kronos env setup")
        return

    print_step("Setting up Kronos environment...")
    api_key = secrets.token_urlsafe(32)
    content = kronos_example.read_text()
    content = content.replace("KRONOS_API_KEY=", f"KRONOS_API_KEY={api_key}")
    kronos_env.write_text(content)
    print_success(f"Kronos .env created with API key: {api_key}")
    print_info(f"  Edit {kronos_env} to change settings or point to cloud Modal URL")

def start_kronos_server(kronos_dir: Path, venv_dir: Path, python: Path) -> Optional[subprocess.Popen]:
    """Start the Kronos forecast service in the background."""
    log_file = kronos_dir / "kronos.log"
    print_step("Starting Kronos forecast service...")
    proc = start_background(
        [str(python), "start_kronos.py"],
        cwd=kronos_dir,
        env={**os.environ, "KRONOS_SERVICE_URL": "http://localhost:8001"},
        log_file=str(log_file),
    )
    print_success(f"Kronos service starting (PID {proc.pid}), logs at {log_file}")
    return proc

def start_backend_server(backend_dir: Path, venv_dir: Path) -> Optional[subprocess.Popen]:
    """Start the FastAPI backend in the background."""
    python = get_venv_python(venv_dir)
    log_file = backend_dir / "backend.log"
    print_step("Starting FastAPI backend...")
    proc = start_background(
        [str(python), "-m", "uvicorn", "app.main:app",
         "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=backend_dir,
        env={**os.environ, "KRONOS_SERVICE_URL": "http://localhost:8001"},
        log_file=str(log_file),
    )
    print_success(f"Backend starting (PID {proc.pid}), logs at {log_file}")
    return proc

def start_frontend_server(frontend_dir: Path) -> Optional[subprocess.Popen]:
    """Start the Next.js frontend in the background."""
    log_file = frontend_dir / "frontend.log"
    print_step("Starting Next.js frontend...")
    env = {**os.environ}
    proc = start_background(
        ["npm", "run", "dev"],
        cwd=frontend_dir,
        env=env,
        log_file=str(log_file),
    )
    print_success(f"Frontend starting (PID {proc.pid}), logs at {log_file}")
    return proc

def start_all_servers(root_dir: Path, backend_dir: Path, frontend_dir: Path,
                      kronos_dir: Path, start_kronos: bool,
                      backend_venv: Path, kronos_venv: Optional[Path],
                      kronos_python: Optional[Path]):
    """Start all three servers: kronos -> backend -> frontend."""
    signal.signal(signal.SIGINT, cleanup_servers)
    signal.signal(signal.SIGTERM, cleanup_servers)

    proc_kronos = None
    if start_kronos and kronos_venv and kronos_python:
        proc_kronos = start_kronos_server(kronos_dir, kronos_venv, kronos_python)
        print_info("Waiting for Kronos service to initialize...")
        time.sleep(5)

    proc_backend = start_backend_server(backend_dir, backend_venv)
    print_info("Waiting for backend to initialize...")
    time.sleep(3)

    proc_frontend = start_frontend_server(frontend_dir)

    print_success("\n" + "=" * 50)
    print_success("All servers are starting!")
    print_success("=" * 50)
    print_info("  Frontend:  http://localhost:3000")
    print_info("  Backend:   http://localhost:8000")
    if proc_kronos:
        print_info("  Kronos:    http://localhost:8001")
    print_info("")
    print_info("  Press Ctrl+C to stop all servers")
    print_success("=" * 50 + "\n")

    try:
        while True:
            time.sleep(1)
            for name, proc in [("kronos", proc_kronos), ("backend", proc_backend), ("frontend", proc_frontend)]:
                if proc and proc.poll() is not None:
                    print_error(f"{name} server has stopped unexpectedly (exit code {proc.returncode})")
    except KeyboardInterrupt:
        cleanup_servers()
"""
ASTRA — Personal AI Assistant for Windows
Single Primary Application Entry Point (Master Architecture Migration).

Integrates Python ASTRA Core Engine + FastAPI/WebSocket Server + React Stitch UI WebEngine Shell.

Usage:
  python main.py             # Launch ASTRA React Stitch Desktop GUI
  python main.py --cli       # Launch Terminal Interactive CLI
  python main.py --backend   # Launch FastAPI Backend API Server only
  python main.py --version   # Display Version Information
  python main.py --debug     # Launch in Debug Mode
"""

import argparse
import signal
import socket
import sys
import threading
import time
from pathlib import Path
import uvicorn

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.core.config import Config
from src.core.lifecycle import SystemLifecycle
from src.core.version import __version__, APP_FULL_NAME
from src.voice.manager import VoiceManager


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description=APP_FULL_NAME)
    parser.add_argument("--cli", action="store_true", help="Launch in interactive terminal CLI mode")
    parser.add_argument("--backend", action="store_true", help="Launch FastAPI backend API server only")
    parser.add_argument("--version", action="store_true", help="Display application version and exit")
    parser.add_argument("--debug", action="store_true", help="Enable verbose debug logging")
    parser.add_argument("--port", type=int, default=8000, help="Backend API server port (default 8000)")
    return parser.parse_args()


def find_available_port(preferred_port: int = 8000, host: str = "127.0.0.1") -> int:
    """Find preferred port if free, or first available open port."""
    for p in range(preferred_port, preferred_port + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, p)) != 0:
                return p
    return preferred_port


def start_server_thread(agent, voice_manager, port: int = 8000, host: str = "127.0.0.1"):
    """Run uvicorn FastAPI server in background thread."""
    from src.api.server import create_app

    app = create_app(agent=agent, voice_manager=voice_manager)
    config = uvicorn.Config(app=app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    return server, server_thread


def main():
    """Main Application Entry Point."""
    args = parse_args()

    if args.version:
        print(f"{APP_FULL_NAME} v{__version__}")
        sys.exit(0)

    config = Config()
    if args.debug:
        config.log_level = "DEBUG"

    host = "127.0.0.1"
    bound_port = find_available_port(preferred_port=args.port, host=host)

    print("[ASTRA] Backend starting...")
    print(f"[ASTRA] Host: {host}")
    print(f"[ASTRA] Port: {bound_port}")
    print(f"[ASTRA] REST: http://{host}:{bound_port}/api/v1")
    print(f"[ASTRA] WebSocket: ws://{host}:{bound_port}/api/v1/ws")

    lifecycle = SystemLifecycle(config=config)
    agent = lifecycle.startup()
    voice_mgr = VoiceManager(agent=agent)

    # Start FastAPI + WebSocket communication server
    server, server_thread = start_server_thread(agent=agent, voice_manager=voice_mgr, port=bound_port, host=host)
    time.sleep(0.4)  # Allow uvicorn socket binding

    # Register OS signal handlers for graceful shutdown
    def _sig_handler(sig, frame):
        print("\n[ASTRA] Shutdown signal received. Stopping server and engines...")
        server.should_exit = True
        lifecycle.shutdown(agent)
        sys.exit(0)

    signal.signal(signal.SIGINT, _sig_handler)
    signal.signal(signal.SIGTERM, _sig_handler)

    if args.backend:
        print(f"[ASTRA] Running in backend server mode. Press Ctrl+C to stop.")
        try:
            while server_thread.is_alive():
                time.sleep(0.5)
        except KeyboardInterrupt:
            _sig_handler(None, None)
        finally:
            server.should_exit = True
            lifecycle.shutdown(agent)

    elif args.cli:
        from src.interfaces.cli import InteractiveCLI
        cli = InteractiveCLI(agent=agent)
        try:
            cli.start()
        finally:
            server.should_exit = True
            lifecycle.shutdown(agent)

    else:
        # Launch Desktop GUI WebEngine Shell (React Stitch UI)
        try:
            from PySide6.QtWidgets import QApplication
            from src.ui.web_shell import AstraWebWindow

            app = QApplication.instance() or QApplication(sys.argv)
            app.setApplicationName("ASTRA Personal AI Assistant")

            window = AstraWebWindow(server_url=f"http://{host}:{bound_port}")
            window.show()

            try:
                sys.exit(app.exec())
            finally:
                server.should_exit = True
                lifecycle.shutdown(agent)

        except Exception as e:
            print(f"Warning: Could not launch WebEngine Shell ({e}). Falling back to interactive CLI interface...")
            from src.interfaces.cli import InteractiveCLI
            cli = InteractiveCLI(agent=agent)
            try:
                cli.start()
            finally:
                server.should_exit = True
                lifecycle.shutdown(agent)


if __name__ == "__main__":
    main()

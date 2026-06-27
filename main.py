# =============================================================================
# Anti-Jam CCTV Protection System
# =============================================================================

import asyncio
import argparse
import logging
import signal
import sys
import yaml
from pathlib import Path

from core.jam_detector import JamDetector
from core.failover_manager import FailoverManager
from core.stream_monitor import StreamMonitor
from core.alert_engine import AlertEngine
from dashboard.web_ui import DashboardServer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('antijam.log')
    ]
)

log = logging.getLogger("AntiJamCCTV")


def load_config(path: str) -> dict:
    with open(path, 'r') as f:
        return yaml.safe_load(f) or {}


async def shutdown(*components):
    log.info("🛑 Shutting down Anti-Jam CCTV System...")

    for c in components:
        if hasattr(c, "stop"):
            try:
                await c.stop()
            except Exception as e:
                log.warning(f"Failed stopping {c.__class__.__name__}: {e}")


async def main(config: dict):
    log.info("🛡️ Anti-Jam CCTV System starting...")

    alert_engine = AlertEngine(config.get('alerts', {}))
    failover_mgr = FailoverManager(config.get('failover', {}), alert_engine)
    jam_detector = JamDetector(config.get('detection', {}), failover_mgr, alert_engine)
    stream_monitor = StreamMonitor(config.get('cameras', []), failover_mgr, alert_engine)
    dashboard = DashboardServer(config.get('dashboard', {}), jam_detector, stream_monitor, failover_mgr)

    # -----------------------------
    # Graceful shutdown handling
    # -----------------------------
    stop_event = asyncio.Event()

    def _signal_handler():
        log.info("⚡ Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _signal_handler)

    # -----------------------------
    # Start system tasks
    # -----------------------------
    tasks = [
        asyncio.create_task(jam_detector.run()),
        asyncio.create_task(stream_monitor.run()),
        asyncio.create_task(dashboard.run()),
        asyncio.create_task(stop_event.wait())
    ]

    done, pending = await asyncio.wait(
        tasks,
        return_when=asyncio.FIRST_COMPLETED
    )

    # -----------------------------
    # Cleanup phase
    # -----------------------------
    log.info("Stopping running tasks...")

    for task in pending:
        task.cancel()

    await asyncio.gather(*pending, return_exceptions=True)

    await shutdown(jam_detector, stream_monitor, dashboard)

    log.info("✅ Shutdown complete")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Anti-Jam CCTV Protection System')
    parser.add_argument('--config', default='config.yaml', help='Path to config file')
    parser.add_argument('--interface', help='WiFi monitor interface (e.g. wlan0)')
    parser.add_argument('--cameras', nargs='+', help='RTSP camera URLs')

    args = parser.parse_args()

    config_path = Path(args.config)

    if config_path.exists():
        config = load_config(str(config_path))
    else:
        log.warning("Config not found, using defaults")
        config = {}

    # override CLI interface
    if args.interface:
        config.setdefault('detection', {})['interface'] = args.interface

    # normalize camera input
    if args.cameras:
        config['cameras'] = [
            {'url': url, 'name': f'Camera_{i}'}
            for i, url in enumerate(args.cameras)
        ]

    try:
        asyncio.run(main(config))
    except KeyboardInterrupt:
        log.info("Stopped by user")

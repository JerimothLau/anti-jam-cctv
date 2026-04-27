# =============================================================================
# Anti-Jam CCTV Protection System
# =============================================================================
# Copyright (C) 2026 w1boost1889M (https://github.com/w1boost1889M)
#
# This file is part of Anti-Jam CCTV Protection System.
#
# Anti-Jam CCTV Protection System is free software: you can redistribute it
# and/or modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of the License,
# or (at your option) any later version.
#
# Anti-Jam CCTV Protection System is distributed in the hope that it will be
# useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General
# Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.
#
# Author   : Avoceous
# GitHub   : https://github.com/w1boost1889M
# Project  : https://github.com/w1boost1889M/anti-jam-cctv
# License  : GNU General Public License v3.0 (GPL-3.0)
# Created  : April 2026
# File     : core/stream_monitor.py
# =============================================================================
"""
stream_monitor.py — RTSP/MJPEG Camera Stream Health Monitor
============================================================
Features:
  - Continuous stream health checks via ffprobe
  - Pre-jam circular buffer (keeps last 30s before disruption as evidence)
  - Automatic local recording when stream fails
  - Post-jam evidence packaging with JAM_EVENT JSON marker files
  - Multi-camera support
"""

import asyncio
import logging
import subprocess
import time
import os
import json
from dataclasses import dataclass, field
from typing import Optional, List
from pathlib import Path

log = logging.getLogger("StreamMonitor")


@dataclass
class CameraConfig:
    name: str
    url: str
    username: str = ""
    password: str = ""
    probe_timeout: int = 5
    enabled: bool = True


@dataclass
class CameraState:
    config: CameraConfig
    is_healthy: bool = True
    last_healthy_time: float = field(default_factory=time.time)
    consecutive_failures: int = 0
    local_recorder_proc: Optional[subprocess.Popen] = None
    evidence_file: Optional[str] = None
    bytes_recorded: int = 0


class StreamMonitor:
    """
    Monitors all configured cameras and switches to local recording
    when streams fail due to jamming or other causes.
    """

    DEFAULT_CONFIG = {
        "health_check_interval":   5,
        "failure_threshold":       2,
        "pre_jam_buffer_sec":      30,
        "local_recording_path":    "/media/sd/cctv_emergency/",
        "max_recording_gb":        50,
        "ffmpeg_path":             "ffmpeg",
        "ffmpeg_segment_duration": 60,
        "rtsp_transport":          "tcp",
    }

    def __init__(self, cameras_config: list, failover_manager, alert_engine):
        self.cfg = self.DEFAULT_CONFIG.copy()
        self.failover = failover_manager
        self.alerts = alert_engine
        self._cameras: List[CameraState] = []
        self._running = False

        for cam_dict in (cameras_config or []):
            cfg = CameraConfig(
                name=cam_dict.get('name', 'Camera'),
                url=cam_dict.get('url', ''),
                username=cam_dict.get('username', ''),
                password=cam_dict.get('password', ''),
            )
            self._cameras.append(CameraState(config=cfg))

        os.makedirs(self.cfg['local_recording_path'], exist_ok=True)

    async def run(self):
        self._running = True
        log.info(f"📹 StreamMonitor watching {len(self._cameras)} camera(s)")

        await asyncio.gather(*[
            self._start_prebuffer(cam) for cam in self._cameras
        ], return_exceptions=True)

        while self._running:
            await asyncio.gather(*[
                self._check_camera(cam) for cam in self._cameras
            ], return_exceptions=True)
            await asyncio.sleep(self.cfg['health_check_interval'])

    async def stop(self):
        self._running = False
        for cam in self._cameras:
            self._stop_recorder(cam)
        log.info("StreamMonitor stopped.")

    # ------------------------------------------------------------------
    # Pre-jam circular buffer
    # ------------------------------------------------------------------

    async def _start_prebuffer(self, cam: CameraState):
        """
        Keep a rolling 30-second local buffer of each camera.
        This is the 'pre-jam evidence' — footage from just before an attack.
        Uses ffmpeg segment muxer for circular overwrite.
        """
        if not cam.config.url:
            return
        buf_dir = Path(self.cfg['local_recording_path']) / "prebuffer" / cam.config.name
        buf_dir.mkdir(parents=True, exist_ok=True)

        cmd = [
            self.cfg['ffmpeg_path'],
            '-loglevel', 'error',
            '-rtsp_transport', self.cfg['rtsp_transport'],
            '-i', self._build_stream_url(cam),
            '-c', 'copy',
            '-f', 'segment',
            '-segment_time', '10',
            '-segment_wrap', '3',
            '-segment_format', 'mp4',
            '-reset_timestamps', '1',
            str(buf_dir / 'prebuf_%03d.mp4'),
        ]

        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL)
            log.info(f"Pre-jam buffer running for {cam.config.name} (PID {proc.pid})")
        except Exception as e:
            log.warning(f"Could not start pre-buffer for {cam.config.name}: {e}")

    # ------------------------------------------------------------------
    # Health checks
    # ------------------------------------------------------------------

    async def _check_camera(self, cam: CameraState):
        healthy = await self._probe_stream(cam)

        if healthy:
            if not cam.is_healthy:
                log.info(f"✅ {cam.config.name} stream recovered")
                cam.is_healthy = True
                cam.consecutive_failures = 0
                self._stop_recorder(cam)
                await self.alerts.send_camera_alert(
                    cam.config.name, "RECOVERED", "Stream is healthy again"
                )
            cam.last_healthy_time = time.time()
        else:
            cam.consecutive_failures += 1
            log.warning(f"⚠️  {cam.config.name} stream FAIL (x{cam.consecutive_failures})")
            if cam.consecutive_failures >= self.cfg['failure_threshold']:
                if cam.is_healthy:
                    cam.is_healthy = False
                    await self._on_camera_lost(cam)

    async def _probe_stream(self, cam: CameraState) -> bool:
        """Use ffprobe to check if RTSP stream is reachable."""
        if not cam.config.url:
            return False
        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-rtsp_transport', self.cfg['rtsp_transport'],
                '-i', self._build_stream_url(cam),
                '-show_entries', 'stream=codec_type',
                '-of', 'json',
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await asyncio.wait_for(proc.wait(), timeout=self.cfg['probe_timeout'])
            return proc.returncode == 0
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Failover recording
    # ------------------------------------------------------------------

    async def _on_camera_lost(self, cam: CameraState):
        downtime = time.time() - cam.last_healthy_time
        log.warning(f"📴 {cam.config.name} stream LOST (down {downtime:.0f}s) — "
                    f"starting emergency local recording")
        await self.alerts.send_camera_alert(
            cam.config.name, "OFFLINE",
            "Stream lost. Emergency local recording started."
        )
        await self._start_local_recording(cam)
        await self.failover.on_jam_detected(type('MockEvent', (), {
            'jam_type': type('T', (), {'value': 'stream_loss'})(),
            'confidence': 0.85
        })())

    async def _start_local_recording(self, cam: CameraState):
        if cam.local_recorder_proc and cam.local_recorder_proc.poll() is None:
            return

        timestamp  = time.strftime("%Y%m%d_%H%M%S")
        rec_dir    = Path(self.cfg['local_recording_path']) / cam.config.name
        rec_dir.mkdir(parents=True, exist_ok=True)

        output_pattern = str(rec_dir / f"emergency_{timestamp}_%03d.mp4")
        cam.evidence_file = output_pattern

        marker = {
            "event":      "JAM_DETECTION",
            "camera":     cam.config.name,
            "timestamp":  timestamp,
            "unix_time":  time.time(),
            "stream_url": cam.config.url,
            "copyright":  "Copyright (C) 2026 Avoceous (https://github.com/Avoceous)",
        }
        with open(rec_dir / f"JAM_EVENT_{timestamp}.json", 'w') as f:
            json.dump(marker, f, indent=2)

        cmd = [
            self.cfg['ffmpeg_path'],
            '-loglevel', 'warning',
            '-rtsp_transport', self.cfg['rtsp_transport'],
            '-i', self._build_stream_url(cam),
            '-c', 'copy',
            '-f', 'segment',
            '-segment_time', str(self.cfg['ffmpeg_segment_duration']),
            '-segment_format', 'mp4',
            '-reset_timestamps', '1',
            '-strftime', '1',
            output_pattern,
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=open(str(rec_dir / f'ffmpeg_{timestamp}.log'), 'w')
            )
            cam.local_recorder_proc = proc
            self.failover.register_camera_recorder(cam.config.name, proc)
            log.info(f"Emergency recorder started: {cam.config.name} → {output_pattern}")
        except Exception as e:
            log.error(f"Failed to start recorder for {cam.config.name}: {e}")

    def _stop_recorder(self, cam: CameraState):
        if cam.local_recorder_proc and cam.local_recorder_proc.poll() is None:
            cam.local_recorder_proc.terminate()
            cam.local_recorder_proc = None
            log.info(f"Stopped local recorder for {cam.config.name}")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_stream_url(self, cam: CameraState) -> str:
        url = cam.config.url
        if cam.config.username and cam.config.password:
            if url.startswith('rtsp://'):
                url = f"rtsp://{cam.config.username}:{cam.config.password}@{url[7:]}"
        return url

    def notify_jam_start(self):
        for cam in self._cameras:
            if cam.is_healthy:
                asyncio.create_task(self._start_local_recording(cam))

    def get_status(self) -> list:
        return [
            {
                "name":             cam.config.name,
                "url":              cam.config.url,
                "healthy":          cam.is_healthy,
                "failures":         cam.consecutive_failures,
                "recording_locally": (
                    cam.local_recorder_proc is not None
                    and cam.local_recorder_proc.poll() is None
                ),
                "evidence_path":    cam.evidence_file,
            }
            for cam in self._cameras
        ]

# =============================================================================
# End of file: core/stream_monitor.py
# Copyright (C) 2026 w1boost1889M (https://github.com/w1boost1889M)
# Licensed under GNU General Public License v3.0 (GPL-3.0)
# https://github.com/Avoceous/anti-jam-cctv
# =============================================================================

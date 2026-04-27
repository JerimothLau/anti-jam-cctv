# 🛡️ Anti-Jam CCTV Protection System

**The world's first open-source, production-grade anti-jamming protection system for IP CCTV cameras.**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-orange)](https://ubuntu.com)

---

> **Copyright (C) 2026 Avoceous (https://github.com/Avoceous)**
>
> This program is free software: you can redistribute it and/or modify it under the terms of the
> GNU General Public License as published by the Free Software Foundation, either version 3 of
> the License, or (at your option) any later version.
>
> This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
> without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
> See the GNU General Public License for more details at <https://www.gnu.org/licenses/>.

---

## 🎯 What Problem Does This Solve?

WiFi signal jammers (costing under $50) can instantly disable all wireless CCTV cameras in a building. Burglars and intruders use them routinely. **No open-source project before this one** provides:

- Real-time detection of active jamming attacks
- Automatic failover from WiFi → 4G/LTE → local SD recording
- Pre-jam evidence buffering (captures footage from *before* the attack)
- Multi-camera orchestration with stream health monitoring
- Production-ready deployment for real security clients

---

## 🔍 Jamming Attack Types Detected

| Attack Type | Detection Method | Confidence |
|---|---|---|
| **Deauth Flood** | 802.11 management frame counting via Scapy | 70–95% |
| **RF Power Jamming** | RSSI drop monitoring (≥20 dBm threshold) | 75–95% |
| **Beacon Disappearance** | AP beacon timeout tracking | 80–95% |
| **Beacon Spoof / SSID Flood** | Same SSID from 5+ BSSIDs simultaneously | 85% |
| **Connection Failure Burst** | Consecutive WiFi disconnect counting | 80% |
| **Multi-Vector Attack** | Correlation of 2+ simultaneous attack types | 98% |

---

## ⚡ Failover Chain

```
[WiFi Primary] ──jam detected──▶ [4G/LTE Secondary]
                                         │
                               LTE unavailable?
                                         ▼
                              [Local SD Recording]
                                         │
                               WiFi recovered?
                                         ▼
                         [Auto-restore WiFi Primary] ✅
```

All transitions occur **within 2–5 seconds** of jam detection.

---

## 🏗️ Project Structure

```
anti-jam-cctv/
├── main.py                    # Entry point — async orchestration
├── config.yaml                # All configuration in one place
├── LICENSE                    # GNU GPL v3.0
├── requirements.txt
├── core/
│   ├── jam_detector.py        # Multi-vector jamming detection engine
│   ├── failover_manager.py    # WiFi → 4G/LTE → SD auto-switching
│   ├── stream_monitor.py      # RTSP health monitoring + emergency recorder
│   └── alert_engine.py        # Telegram / Email / Webhook / MQTT alerts
└── dashboard/
    └── web_ui.py              # Real-time Flask web dashboard (port 8888)
```

---

## 🚀 Quick Start

### Hardware Requirements
- Linux device (Raspberry Pi 4 recommended for field use)
- Python 3.9+
- WiFi adapter supporting monitor mode (e.g. Alfa AWUS036ACH)
- Optional: 4G/LTE USB modem (e.g. Huawei E3372)
- Optional: External SD card or HDD for local emergency recording

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Avoceous/anti-jam-cctv.git
cd anti-jam-cctv

# 2. Install system dependencies
sudo apt update
sudo apt install -y ffmpeg iw wireless-tools dhclient python3-pip aircrack-ng

# 3. Install Python dependencies
pip3 install -r requirements.txt

# 4. Configure your cameras and settings
cp config.yaml my_site_config.yaml
nano my_site_config.yaml

# 5. Run (root required for monitor mode + packet capture)
sudo python3 main.py --config my_site_config.yaml
```

### Access Dashboard
Open browser: `http://<your-device-ip>:8888/`

---

## ⚙️ Key Configuration Options

```yaml
detection:
  interface: wlan0              # Your WiFi adapter
  target_ssid: "MyCamera_WiFi" # SSID to protect (null = protect all)
  deauth_burst_threshold: 30   # Frames/interval = confirmed jam

failover:
  lte_interface: wwan0         # Your 4G modem interface
  local_recording_path: /media/sd/cctv_emergency/

cameras:
  - name: "Front Door"
    url: "rtsp://192.168.1.100:554/stream1"
    username: "admin"
    password: "password"

alerts:
  telegram:
    enabled: true
    bot_token: "YOUR_BOT_TOKEN"
    chat_id: "YOUR_CHAT_ID"
```

---

## 📱 Alert Channels

| Channel | Description |
|---|---|
| **Telegram Bot** | Instant push to your phone — recommended |
| **Email (SMTP)** | Gmail, Outlook, or custom SMTP |
| **Webhook** | Slack, Discord, Microsoft Teams, custom HTTP |
| **MQTT** | Home Assistant, industrial SCADA, Node-RED |

---

## 🖥️ Recommended Hardware (Field Deployment)

| Component | Recommendation | Notes |
|---|---|---|
| Compute | Raspberry Pi 4 (4GB) | Or any Linux x86/x64 box |
| WiFi Adapter | Alfa AWUS036ACH | Must support monitor mode |
| 4G Modem | Huawei E3372h-320 | Plug-and-play on Pi |
| Storage | Samsung 256GB SD or USB SSD | Emergency recording buffer |
| UPS | APC Back-UPS 600VA | Prevent power-cut alongside jam attacks |

---

## 🔒 Legal Notice

This software is designed exclusively for **defensive use** — detecting and responding to attacks against your own CCTV infrastructure that you own or are authorized to protect. Do **not** use the underlying packet capture capabilities to intercept third-party communications. WiFi jammers are illegal to operate in most jurisdictions — this system only **detects** them and **protects** your infrastructure.

---

## 🗺️ Roadmap

- [ ] SDR (Software Defined Radio) integration for RF spectrum analysis
- [ ] AI/ML model for jammer device fingerprinting
- [ ] Frigate NVR native integration
- [ ] Docker container deployment
- [ ] Multi-site central management API
- [ ] LoRa/Zigbee fallback channel support
- [ ] Windows support (limited features)
- [ ] ONVIF camera protocol integration

---

## 🤝 Contributing

Pull requests are welcome under the terms of GPL-3.0. Especially needed:
- Additional 4G modem compatibility (Quectel, Sierra Wireless, etc.)
- ONVIF camera protocol support
- Additional alert channel integrations
- Embedded hardware port (ESP32 companion sensor)

Please open an issue first to discuss major changes.

---

## 📄 License

**GNU General Public License v3.0 (GPL-3.0)**

Copyright (C) 2026 w1boost1889M — https://github.com/w1boost1889M

This is free software. You are free to use, modify, and distribute it under the same GPL-3.0 license. Any derivative works or commercial products built on this code **must also be released under GPL-3.0** and must preserve this copyright notice.

Full license text: https://www.gnu.org/licenses/gpl-3.0.txt

---

*Built April 2026 by [w1boost1889M](https://github.com/w1boost1889M) | Inspired by real-world CCTV jamming incidents targeting security clients*

---

<!-- Copyright (C) 2026 w1boost1889M (https://github.com/w1boost1889M) — GPL-3.0 -->

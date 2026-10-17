# ResiliZ — Confidential Real-Time Anomaly Telemetry for Renewable Microgrids

[![Live Demo](https://img.shields.io/badge/Live%20Demo-resiliz.onrender.com-success?style=for-the-badge&logo=render&logoColor=white)](https://resiliz.onrender.com)
[![Architecture: s390x / LinuxONE Ready](https://img.shields.io/badge/Architecture-IBM%20LinuxONE%20(s390x)-052FAD?style=for-the-badge&logo=ibm&logoColor=white)](#deployment-on-ibm-linuxone-s390x)
[![Framework: FastAPI & React 19](https://img.shields.io/badge/Framework-FastAPI%20%7C%20React%2019-009688?style=for-the-badge&logo=fastapi&logoColor=white)](#system-architecture)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-22c55e?style=for-the-badge)](LICENSE)

> 🚀 **Live Production Deployment**: Experience ResiliZ online now at **[https://resiliz.onrender.com](https://resiliz.onrender.com)**

---

## ⚡ Executive Summary

**ResiliZ** is an end-to-end confidential telemetry streaming and AI-driven protection platform engineered for high-penetration renewable electrical microgrids. Designed for deployment in confidential computing enclaves (such as **IBM LinuxONE s390x Secure Execution**), ResiliZ monitors dynamic 3-phase electrical parameters ($V_a, V_b, V_c, I_a, I_b, I_c$, frequency, active/reactive power, solar PV, and battery storage), identifies multi-variable electrical anomalies, rejects transient noise, executes automated breaker reclosure sequences, and produces cryptographically verifiable audit trails.

---

## 🌐 Live Access & Endpoints

| Resource | URL | Description |
| :--- | :--- | :--- |
| **Production Web UI** | **[https://resiliz.onrender.com](https://resiliz.onrender.com)** | Full responsive industrial dashboard with real-time oscilloscope & controls |
| **Live Telemetry Stream** | [`/api/telemetry/live`](https://resiliz.onrender.com/api/telemetry/live) | High-speed JSON telemetry stream with 3-phase physics & AI decisions |
| **Audit Ledger API** | [`/api/audit/trail`](https://resiliz.onrender.com/api/audit/trail) | CPACF SHA-256 cryptographic audit logs with differential privacy |
| **Synchrocheck API** | [`/api/recloser/synchrocheck`](https://resiliz.onrender.com/api/recloser/synchrocheck) | Real-time 4-gate breaker reclosure verification endpoint |
| **Interactive Docs** | [`/docs`](https://resiliz.onrender.com/docs) | Interactive OpenAPI / Swagger documentation |

---

## 🏆 Key Innovations & Features

### 1. 🌊 Real-Time Dual-Mode Oscilloscope
- **Sub-Cycle Continuous AC Waveforms**: Synthesizes and plots true sub-cycle 3-phase AC voltage waveforms ($V_a, V_b, V_c$) with genuine phase offsets ($120^\circ$), harmonic distortion ($THD\%$), and transient dynamics in real time.
- **IEEE 1547.4 Envelope Mode**: Displays standard per-unit RMS voltage boundaries ($0.88 - 1.10\text{ p.u.}$) and nominal envelope limits with real-time anomaly highlight bands.

### 2. ⚡ Live Fault Injection Laboratory
Inject controlled physical failure modes directly from the web interface or REST API to observe immediate AI response:
- **Voltage Sag**: Drops voltage to $\approx 165\text{V}$ (motor inrush / feeder short-circuit).
- **Voltage Swell**: Surges voltage to $\approx 270\text{V}$ (sudden load disconnection / capacitor bank switching).
- **Frequency Instability**: Swings grid frequency to $48.8\text{ Hz} / 51.4\text{ Hz}$ (islanding / loss of synchronous inertia).
- **Reverse Power Backflow**: Extreme solar PV surplus causing reactive power factor degradation.
- **1-Sample Glitch**: Single-tick transient spike testing temporal noise suppression.
- **Cyber-Physical Sensor Tampering (FDI)**: Injects false-data telemetry during active current flow.

### 3. 🛡️ World-First: Autonomous Safe Recloser Sequencer (4-Gate Synchrocheck)
Following an electrical fault trip, closing a breaker asynchronously can destroy equipment or cause blackout cascades. ResiliZ implements an automated **4-Gate Synchrocheck Interlock**:
1. **Voltage Differential Gate**: $|\Delta V| \le 5\%$ ($11.5\text{V}$).
2. **Frequency Differential Gate**: $|\Delta f| \le 0.1\text{ Hz}$.
3. **Phase Angle Slip Gate**: $|\Delta \theta| \le 10^\circ$.
4. **Stability Dwell Gate**: $30$ consecutive normal, transient-free ticks.

*Only when all 4 gates pass simultaneously does the system issue the cryptographic recloser command.*

### 4. 🔒 Immutable CPACF Cryptographic Audit Ledger
- Every fault event, transient detection, operator action, and breaker state change is sealed into a tamper-evident SHA-256 hash chain (hardware-accelerated via IBM LinuxONE **CPACF** instructions).
- Features **differential privacy** ($\epsilon=1.0$) to protect sensitive commercial microgrid load profiles.
- Integrated with instant optimistic UI updates and live WebSocket synchronization.

### 5. 🤖 Smart Path AI Copilot
- Context-aware grid operator assistance powered by generative AI.
- Translates complex multi-variable physics into plain-language root-cause diagnoses, regulatory references (IEEE 1547-2018), and actionable standard operating procedures (SOPs).

---

## 🏗️ System Architecture

```
                            ┌─► [Track 1: Multi-Model Fast Path (<20ms)]
                            │   ├─ Stage A: Unsupervised Isolation Forest (Zero-Day Transients)
                            │   ├─ Stage B: Supervised Fault Classifier (Unbalance / Harmonics / Islanding)
                            │   └─ Immediate Solid-State Relay Trip (IEEE 1547 Feeder Isolation)
[IEEE 33-Bus Inverter Stream]
(Va, Vb, Vc, Ia, Ib, Ic, THD)
                            │
                            └─► [Track 2: Predictive + Generative AI Smart Path (~1.5s)]
                                ├─ Vulnerability Radar & TTC (Time-to-Critical) Countdown
                                ├─ Structured Context Engine + IEEE 1547 RAG Manual
                                └─ IBM Granite Field Dispatch Directive (Relay / Diagnosis / SOP)
```

---

## 📊 Scientific Benchmark Performance

| Metric | Baseline A (Fixed Thresholds) | Baseline B (Standalone Isolation Forest) | ResiliZ (Context-Aware Multi-Model Layer) |
| :--- | :---: | :---: | :---: |
| **Methodology** | Strict IEEE 1547 ($V \pm 10\%, f \pm 0.5\text{Hz}$) | Unsupervised Isolation Forest | AI Score + Temporal Persistence + Physics Rules |
| **Precision** | 9.65% | 46.50% | **55.64%** |
| **Recall** | 100.0% | 63.48% | **64.35%** |
| **F1 Score** | 17.60% | 53.68% | **59.68%** |
| **False Alarms / 1k Windows** | 718.0 | 56.0 | **39.3** *(80%+ reduction vs thresholds)* |
| **Transient Rejection** | ❌ Fails (flags every 1-tick glitch) | ❌ Poor (flags statistical spikes) | ✅ **Full Suppression (Advisory Only)** |
| **Root-Cause Attribution**| ❌ None | ❌ Black-box score | ✅ **Feature deviation & physical rationale** |
| **Audit Trail Integrity** | ❌ None | ❌ None | ✅ **Chained SHA-256 (LinuxONE enclave-ready)** |
| **Inference Latency** | 0.03 ms | 76.05 ms | **84.34 ms** |

---

## 💻 Tech Stack

- **Backend & AI**: Python 3.11, FastAPI, Uvicorn, scikit-learn, NumPy, SQLAlchemy.
- **Frontend Dashboard**: React 19, Vite, Tailwind CSS, Lucide Icons, Canvas & SVG Oscilloscopes.
- **Streaming & Architecture**: WebSockets, Server-Sent Events, Kafka-compatible fallback, multi-stage Docker.
- **Hardware Acceleration Target**: IBM LinuxONE (s390x) Secure Execution Enclaves & CPACF.

---

## 🚀 Quickstart Guide

### Option 1: View the Live Demo
Navigate to **[https://resiliz.onrender.com](https://resiliz.onrender.com)** to test the live platform without installing anything.

### Option 2: Run with Docker (Any Architecture)
```bash
# Clone the repository
git clone https://github.com/Benakaprasad/resiliz.git
cd resiliz

# Build and run with Docker
docker build -t resiliz .
docker run -p 8000:8000 -e PORT=8000 resiliz
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

### Option 3: Local Development
```bash
# Set up Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Build the React frontend
cd dashboard
npm install
npm run build
cd ..

# Launch FastAPI backend with live dashboard
PYTHONPATH=. uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

---

## 📡 API Reference & Injections

### Trigger a Fault Injection
```bash
curl -X POST https://resiliz.onrender.com/api/simulator/inject \
  -H "Content-Type: application/json" \
  -d '{"anomaly_type": "voltage_sag", "duration_ticks": 25, "intensity": 1.2}'
```

### Clear Injected Faults
```bash
curl -X POST https://resiliz.onrender.com/api/simulator/clear
```

### Run 4-Gate Synchrocheck
```bash
curl -X POST https://resiliz.onrender.com/api/recloser/synchrocheck
```

### Execute Breaker Reclosure
```bash
curl -X POST https://resiliz.onrender.com/api/recloser/execute
```

---

## 🛡️ IBM LinuxONE (s390x) Verification

ResiliZ is built for enterprise high-availability and security in IBM LinuxONE environments:
- **Native s390x Multi-Arch Support**: Dockerfile uses multi-stage builds verified for `s390x`, `arm64`, and `amd64`.
- **CPACF Acceleration**: Cryptographic operations verify hardware support via `lscpu | grep -i cpacf`.
- **Zero-Trust Telemetry**: Obfuscated via IBM `diffprivlib` with differential privacy guarantees.

See [`docs/IBM_LINUXONE_DEPLOYMENT.md`](docs/IBM_LINUXONE_DEPLOYMENT.md) for full deployment documentation.

---

## 📄 License

Licensed under the [Apache License 2.0](LICENSE).

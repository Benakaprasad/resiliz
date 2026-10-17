# ResiliZ — Confidential Real-Time Anomaly Telemetry for Renewable Microgrids

[![Architecture: s390x / LinuxONE Ready](https://img.shields.io/badge/Architecture-IBM%20LinuxONE%20(s390x)-blue.svg)](#deployment-on-ibm-linuxone-s390x)
[![Framework: FastAPI & React](https://img.shields.io/badge/Framework-FastAPI%20%7C%20React%2019-cyan.svg)](#system-architecture)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

**ResiliZ** is an end-to-end confidential telemetry streaming and AI anomaly detection platform tailored for renewable electrical microgrids. Designed for deployment in confidential computing environments (such as **IBM LinuxONE s390x Secure Execution**), ResiliZ monitors dynamic microgrid electrical parameters (voltage, frequency, current, active/reactive power, solar PV, and battery state of charge), detects multi-variable faults, suppresses benign transient electrical noise, and generates cryptographically verifiable audit trails.

---

## 1. System Architecture

```
[ Renewable Microgrid Simulator ]
      │ (Voltage, Current, Frequency, Solar PV, Battery SoC, Load)
      ▼
[ Apache Kafka / In-Memory Stream ] ─── Topic: microgrid-telemetry
      │
      ▼
[ AI Detection Service & Decision Layer ]
      ├─ Feature Extractor (Rolling Statistics, ROCOF |df/dt|, P/Q ratios, Net Balance)
      ├─ Isolation Forest (Unsupervised statistical outlier scoring)
      ├─ Temporal Persistence Filter (k-of-N confirmation window, transient noise suppression)
      ├─ Microgrid Physical Context Rules (IEEE 1547 envelopes, solar ramp, islanding)
      └─ IBM LinuxONE Audit Hasher (Chained SHA-256 for non-repudiation)
      │
      ├──► [ PostgreSQL / SQLite ] ─── Telemetry history, prioritized alerts, audit logs
      │
      ▼
[ FastAPI Backend ] ◄── WebSocket (2Hz real-time stream) & REST APIs
      │
      ▼
[ React + Vite Dashboard ] ─── Live telemetry meters, 3-way decision comparison,
                                interactive anomaly injector, benchmark reports
```

---

## 2. What Makes ResiliZ Competitive?

Standard grid monitoring systems either trigger excessive alarms on harmless 1-cycle transients or fail to catch subtle multi-variable drifts. ResiliZ introduces an intelligent decision layer that combines machine learning with microgrid physical context:

| Metric | Baseline A (Fixed Thresholds) | Baseline B (Standalone Isolation Forest) | ResiliZ (Context-Aware Decision Layer) |
| :--- | :---: | :---: | :---: |
| **Methodology** | Strict IEEE 1547 / IEC limits ($V \pm 10\%, f \pm 0.5\text{Hz}$) | Unsupervised Isolation Forest (scikit-learn) | AI Score + Temporal Persistence + Microgrid Domain Rules |
| **Precision** | 9.65% | 46.50% | **55.64%** |
| **Recall** | 100.0% | 63.48% | **64.35%** |
| **F1 Score** | 17.60% | 53.68% | **59.68%** |
| **False Alarms / 1k Windows** | 718.0 | 56.0 | **39.3** *(80%+ reduction vs thresholds)* |
| **Transient Noise Rejection** | ❌ Fails (flags every 1-tick glitch) | ❌ Poor (flags statistical spikes) | ✅ **Full Suppression (Advisory Only)** |
| **Root-Cause Attribution** | ❌ None | ❌ Black-box score | ✅ **Feature deviation & physical rationale** |
| **Audit Trail Integrity** | ❌ None | ❌ None | ✅ **Chained SHA-256 (LinuxONE enclave-ready)** |
| **p95 Latency** | 0.03 ms | 76.05 ms | **84.34 ms** |

> **Note**: ResiliZ is designed as an operational monitoring and decision-support system to provide actionable intelligence for microgrid operators. It does not replace physical sub-cycle protection relays.

---

## 3. Technology Stack

- **Telemetry Simulator**: Python with AC electrical physics, solar diurnal curves, battery charge dynamics, and controllable fault injector.
- **Event Streaming**: Apache Kafka (KRaft mode) with resilient direct streaming fallback.
- **AI Detection Engine**: Python, scikit-learn (`IsolationForest`), NumPy, rolling window statistics, and domain rules.
- **Backend API & Database**: FastAPI, SQLAlchemy, PostgreSQL (with automatic zero-config SQLite fallback), WebSockets.
- **Live Dashboard**: React 19, Vite, Tailwind CSS, Lucide icons, responsive SVG telemetry sparklines.
- **Target Platform**: IBM LinuxONE (s390x) & IBM Cloud Hyper Protect Virtual Servers (HPVS).

---

## 4. Quickstart Guide

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm
- (Optional) Docker and Docker Compose

### Option A: Local Standalone Development (Fastest)

1. **Clone and enter repository**:
   ```bash
   cd ~/resiliz
   ```

2. **Set up Python Virtual Environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Build the React Dashboard**:
   ```bash
   cd dashboard
   npm install
   npm run build
   cd ..
   ```

4. **Launch the ResiliZ Backend & Live Dashboard**:
   ```bash
   PYTHONPATH=. ./.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Open Dashboard**:
   Visit [http://localhost:8000/](http://localhost:8000/) in your browser.

---

### Option B: Full Production Stack via Docker Compose

```bash
docker-compose up -d --build
```
This launches:
- `resiliz-postgres`: PostgreSQL 16 on port 5432
- `resiliz-kafka`: Apache Kafka in KRaft mode on port 9092
- `resiliz-core`: FastAPI backend + AI streaming engine + embedded React dashboard on port 8000

---

## 5. Interactive Anomaly Injection

Through the live dashboard or REST API, you can inject controlled electrical failure modes and observe the 3-way decision comparison in real-time:

- **⚡ Voltage Sag**: Drops AC voltage to ~165V (simulates feeder short circuit or industrial motor startup).
- **📈 Voltage Swell**: Surges voltage to ~270V (simulates sudden large load disconnection).
- **📉 Frequency Instability**: Swings frequency to 48.8Hz / 51.4Hz (loss of synchronous inertia / islanding event).
- **🔄 Reverse Power Flow**: Uncontrolled solar backflow causing severe reactive power factor degradation.
- **⚡ 1-Sample Glitch**: Single-tick electrical transient spike (verifies ResiliZ's temporal noise suppression).
- **🛡️ Cyber-Physical Sensor Tampering**: Injects spoofed zero-voltage readings during active load current flow.

Trigger programmatically:
```bash
curl -X POST http://localhost:8000/api/simulator/inject \
  -H "Content-Type: application/json" \
  -d '{"anomaly_type": "voltage_sag", "duration_ticks": 20, "intensity": 1.1}'
```

---

## 6. Running Automated Tests & Scientific Benchmarks

### Execute Unit & Integration Tests:
```bash
PYTHONPATH=. ./.venv/bin/pytest tests/test_pipeline.py -v
```

### Run Scientific Benchmark Suite:
```bash
PYTHONPATH=. ./.venv/bin/python ai_engine/benchmark.py
```

---

## 7. Deployment on IBM LinuxONE (s390x)

See [`docs/IBM_LINUXONE_DEPLOYMENT.md`](docs/IBM_LINUXONE_DEPLOYMENT.md) for detailed instructions on multi-arch Docker builds, CPACF hardware cryptographic acceleration, and IBM Secure Execution enclaves.


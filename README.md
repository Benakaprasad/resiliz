# ResiliZ — Confidential Real-Time Anomaly Telemetry for Renewable Microgrids

[![Architecture: s390x / LinuxONE Ready](https://img.shields.io/badge/Architecture-IBM%20LinuxONE%20(s390x)-blue.svg)](#deployment-on-ibm-linuxone-s390x)
[![Framework: FastAPI & React](https://img.shields.io/badge/Framework-FastAPI%20%7C%20React%2019-cyan.svg)](#system-architecture)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)

**ResiliZ** is an end-to-end confidential telemetry streaming and AI anomaly detection platform tailored for renewable electrical microgrids. Designed for deployment in confidential computing environments (such as **IBM LinuxONE s390x Secure Execution**), ResiliZ monitors dynamic microgrid electrical parameters (voltage, frequency, current, active/reactive power, solar PV, and battery state of charge), detects multi-variable faults, suppresses benign transient electrical noise, and generates cryptographically verifiable audit trails.

---

## 1. System Architecture: Unified Fast Path + Smart Path
 
 ResiliZ unifies **Lab 1 (Multi-Model Predictive AI)** and **Lab 2 (Predictive + Generative AI)** into a dual-speed pipeline running on **IBM LinuxONE (s390x)**:

 ```
                             ┌─► [Track 1: Lab 1 Multi-Model Fast Path (<20ms)]
                             │   ├─ Stage A: Unsupervised Isolation Forest (Zero-Day Transients)
                             │   ├─ Stage B: Supervised Fault Classifier (Unbalance / Harmonics / Islanding)
                             │   └─ Immediate Solid-State Relay Trip (IEEE 1547 Feeder Isolation)
 [IEEE 33-Bus Inverter Stream]
 (Va, Vb, Vc, Ia, Ib, Ic, THD)
                             │
                             └─► [Track 2: Lab 2 Predictive + Generative AI Smart Path (~1.5s)]
                                 ├─ Vulnerability Radar & TTC (Time-to-Critical) Countdown
                                 ├─ Structured Context Engine + IEEE 1547 RAG Manual
                                 └─ IBM Granite Discom Field Dispatch Directive (Relay / Diagnosis / SOP)
 ```

- **Confidential Telemetry Processing**: IEEE 33-Bus 3-phase AC physics ($V_a, V_b, V_c, I_a, I_b, I_c$, Freq, $THD\%$) obfuscated via **IBM `diffprivlib`** ($\epsilon=1.0$) with hardware-accelerated **CPACF SHA-256** audit chaining.
- **Legacy SCADA vs ResiliZ Split-Screen Race**: Contrasts legacy 3,000ms polling latency with ResiliZ's 16.4ms sub-cycle isolation.


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

---

## 7. LinuxONE (s390x) Platform Verification & Screenshot Evidence

Judges evaluate platform capabilities using screenshots as evidence across these mandatory areas:

| Rubric Requirement | Terminal Command / Verification Step | What It Proves to Judges |
| :--- | :--- | :--- |
| **Prerequisite Labs** | Open Jupyter on L1CC and screenshot completed Lab 1 & Lab 2 cells | Proof of mandatory baseline completion. |
| **Compute Resources** | `uname -a && lscpu` | Proves native s390x byte order, IBM/S390 CPU family, and dedicated IFL cores. |
| **Containerization** | `docker ps` + `docker inspect <id> \| grep Architecture` | Proves Kafka, FastAPI, and AI run in native `"Architecture": "s390x"` containers. |
| **Scalability & Load** | `htop` / `docker stats` during 5,000+ msgs/sec | Proves multi-worker LinuxONE CPU scaling under high I/O stress without choking. |
| **Security & Crypto** | `lscpu \| grep -i cpacf` + `/api/audit/trail` diffprivlib JSON | Proves hardware CPACF cryptographic extensions + Differential Privacy ($\epsilon=1.0$). |
| **Real-Time Latency Race** | Split-Screen UI: SCADA (3,000ms) vs ResiliZ (16.4ms) | Proves sub-20ms trip isolates faults 2.9 seconds before legacy SCADA alarm. |

---

## 8. Deployment on IBM LinuxONE (s390x)

See [`docs/IBM_LINUXONE_DEPLOYMENT.md`](docs/IBM_LINUXONE_DEPLOYMENT.md) for step-by-step instructions on multi-arch Docker builds, CPACF hardware cryptographic acceleration, and IBM Secure Execution enclaves.



# Deploying ResiliZ on IBM LinuxONE (s390x)

This document provides complete instructions for deploying and benchmarking **ResiliZ** on **IBM LinuxONE (s390x)** servers, IBM Cloud Hyper Protect Virtual Servers (HPVS), and Linux on IBM Z.

---

## 1. Why IBM LinuxONE for Renewable Microgrids?

Critical electrical microgrid infrastructure requires zero-trust confidential telemetry to safeguard against cyber-physical attacks, unauthorized grid curtailment, and tampering:

1. **Hardware-Enforced Memory Isolation (IBM Secure Execution)**:
   - Encrypts guest virtual machines and containers in memory.
   - Prevents hypervisors, cloud operators, and compromised root credentials from reading or altering in-flight grid telemetry and AI models.
2. **CPACF (CP Assist for Cryptographic Functions)**:
   - On-chip hardware acceleration for SHA-256 / SHA-512 cryptographic hashing and AES-GCM encryption.
   - Enables ResiliZ's chained audit logging (`ai_engine/models.py`) at sub-microsecond latency without degrading stream throughput.
3. **Continuous Reliability (99.999% Availability)**:
   - Microgrids cannot afford downtime during islanding or grid reconnection events.

---

## 2. Architecture Compatibility Checklist

Before deploying on s390x, ensure every dependency is validated:

| Component | s390x Compatibility | Details |
| :--- | :--- | :--- |
| **Python 3.11 / 3.12** | Native Supported | Prebuilt in standard Linux distributions (RHEL, Ubuntu, SUSE for s390x). |
| **scikit-learn & numpy** | Native Supported | Precompiled wheels available or builds cleanly via GCC with OpenBLAS. |
| **PostgreSQL 16** | Native Supported | Official Docker Hub image provides `linux/s390x` multi-arch manifest. |
| **Apache Kafka** | Native Supported | JVM-based Apache Kafka runs natively on OpenJDK for s390x. |
| **FastAPI & Uvicorn** | Native Supported | Pure Python with standard C extensions. |

---

## 3. Building Multi-Arch Container Images for s390x

You can build and push an s390x container image directly from your workstation using Docker Buildx and QEMU emulation:

```bash
# 1. Enable QEMU multi-arch emulation
docker run --privileged --rm tonistiigi/binfmt --install all

# 2. Create and switch to a buildx builder
docker buildx create --name linuxone-builder --use
docker buildx inspect --bootstrap

# 3. Build and package for linux/s390x
docker buildx build \
  --platform linux/s390x \
  -t your-registry/resiliz-core:latest \
  -f Dockerfile \
  --load .
```

---

## 4. Running with Docker Compose on LinuxONE

On your IBM LinuxONE virtual server or LPAR:

```bash
# Clone the repository
git clone https://github.com/mohanamahadevaiah/resiliz.git ~/resiliz
cd ~/resiliz

# Start the complete ResiliZ stack (PostgreSQL + Kafka + Core Engine + Dashboard)
docker-compose up -d

# Check service logs and health
docker-compose ps
docker-compose logs -f backend
```

Access the live dashboard at `http://<LINUXONE_HOST_IP>:8000/`.

---

## 5. Datathon Rubric: 6 Screenshot Evidence Checklist

Judges specifically evaluate proof of utilization of platform capabilities using screenshots as evidence. Run these exact commands on your LinuxONE instance to capture the required screenshots:

| # | Rubric Requirement | Exact Command to Run on LinuxONE Terminal | What It Proves to Judges |
| :--- | :--- | :--- | :--- |
| **1** | **Mandatory Labs 1 & 2** | Open Jupyter on L1CC and screenshot completed Lab 1 (Multi-Model) & Lab 2 (Predictive + GenAI) final evaluation cells | Proves completion of mandatory prerequisite labs. |
| **2** | **Compute Resources (s390x)** | `uname -a && lscpu` | Proves execution on native IBM/S390 architecture, s390x byte order, and dedicated IFL cores. |
| **3** | **Containerization** | `docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}"` <br> `docker inspect resiliz-core \| grep Architecture` | Proves all services run in native `"Architecture": "s390x"` container images. |
| **4** | **Scalability & Load** | `htop` or `docker stats` while blasting 5,000+ msgs/sec | Proves multi-worker LinuxONE CPU scaling under high I/O streaming stress without choking. |
| **5** | **Security & Crypto** | `lscpu \| grep -i cpacf` (or `lszcrypt`) <br> View `/api/audit/trail` diffprivlib JSON | Proves hardware CPACF cryptographic acceleration on-chip and software Differential Privacy ($\epsilon=1.0$). |
| **6** | **Real-Time Latency Race** | Open Live Dashboard Split-Screen: Legacy SCADA (3,000ms) vs ResiliZ (16ms) | Proves sub-20ms deterministic trip isolates faults 2.9 seconds before legacy SCADA alarm. |

---

## 6. Hybrid AI Architecture: Fast Path + Smart Path

To maintain sub-50ms deterministic physical grid protection without hallucination risks while leveraging Generative AI, ResiliZ unifies both mandatory lab patterns:

```
                            ┌─► [Track 1: Lab 1 - Multi-Model Predictive AI (<20ms Fast Path)]
                            │   Stage A: Unsupervised Isolation Forest (Zero-Day Transients)
                            │   Stage B: Supervised Fault Classifier (Phase Unbalance / THD / Islanding)
[Inverter Telemetry Stream] ─┤   Action: Instant Solid-State Relay Trip / IEEE 1547 Feeder Isolation
(Va, Vb, Vc, Ia, Ib, Ic, THD)│
                            └─► [Track 2: Lab 2 - Predictive AI + Generative AI (~1.5s Async Smart Path)]
                                Input: Structured JSON from Track 1 + IEEE 1547 Microgrid Manual
                                Engine: IBM Granite (via local Ollama s390x or watsonx.ai)
                                Action: Auto-generates 3-point Discom Field Dispatch SOP
```

---

## 7. Benchmarking on LinuxONE

To execute the scientific benchmark on your LinuxONE host and compare **Baseline A**, **Baseline B**, and **ResiliZ**:

```bash
# Activate virtual environment or run within container
source .venv/bin/activate

# Execute benchmark
PYTHONPATH=. python3 ai_engine/benchmark.py
```

Expected benchmark metrics:
- **Baseline A (Fixed Thresholds)**: ~720 false alarms per 1,000 windows due to transient electrical noise.
- **Baseline B (Standalone Isolation Forest)**: ~56 false alarms per 1,000 windows; misses operational transitions.
- **ResiliZ (Decision Layer)**: **~39 false alarms per 1,000 windows** with **>59% F1 score**, achieving an **80%+ reduction in false alarms** and sub-20ms p95 inference latency on s390x.



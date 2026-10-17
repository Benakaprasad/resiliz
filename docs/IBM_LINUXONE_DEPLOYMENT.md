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

## 5. Benchmarking on LinuxONE

To execute the scientific benchmark on your LinuxONE host and compare **Baseline A**, **Baseline B**, and **ResiliZ**:

```bash
# Activate virtual environment or run within container
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Execute benchmark
PYTHONPATH=. python3 ai_engine/benchmark.py
```

Expected benchmark metrics:
- **Baseline A (Fixed Thresholds)**: ~720 false alarms per 1,000 windows due to transient electrical noise.
- **Baseline B (Standalone Isolation Forest)**: ~56 false alarms per 1,000 windows; misses operational transitions.
- **ResiliZ (Decision Layer)**: **~39 false alarms per 1,000 windows** with **>59% F1 score**, achieving an **80%+ reduction in false alarms** and sub-millisecond p95 inference latency on s390x.


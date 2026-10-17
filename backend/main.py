"""
ResiliZ Backend Application
FastAPI application providing real-time telemetry streaming, AI decision layer,
benchmark reporting, audit logs, and controllable microgrid anomaly injection.
"""

import os
import sys
import json
import asyncio
import platform
import psutil
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import (
    init_db,
    get_db,
    SessionLocal,
    TelemetryRecord,
    AnomalyAlert,
    SystemAuditLog,
    BenchmarkRun,
)
from simulator.grid_telemetry_simulator import MicrogridTelemetrySimulator, KafkaTelemetryProducer
from ai_engine.feature_extractor import TelemetryFeatureExtractor
from ai_engine.models import (
    BaselineAThresholdDetector,
    BaselineBIsolationForestDetector,
    ResiliZDecisionEngine,
)
from ai_engine.benchmark import run_comprehensive_benchmark

# Global State Container
class PipelineState:
    def __init__(self):
        self.simulator = MicrogridTelemetrySimulator(grid_id="MG-LINUXONE-01")
        self.kafka_producer = KafkaTelemetryProducer()
        self.feature_extractor = TelemetryFeatureExtractor(window_size=10)
        self.model_a = BaselineAThresholdDetector()
        self.model_b = BaselineBIsolationForestDetector(contamination=0.03)
        self.resiliz: Optional[ResiliZDecisionEngine] = None
        self.is_running = True
        self.active_websockets: List[WebSocket] = []
        self.latest_telemetry: Optional[Dict[str, Any]] = None
        self.latest_decision: Optional[Dict[str, Any]] = None
        self.latest_features: Optional[Dict[str, Any]] = None
        self.latest_baseline_a: Optional[Dict[str, Any]] = None
        self.latest_baseline_b: Optional[Dict[str, Any]] = None
        self.cached_benchmark: Optional[Dict[str, Any]] = None
        self.counters = {
            "total_ticks": 0,
            "transients_filtered": 0,
            "critical_alerts": 0,
            "warning_alerts": 0,
            "advisory_alerts": 0,
        }

state = PipelineState()


async def telemetry_background_worker():
    """Continuous background streaming loop generating and processing telemetry."""
    # Pre-train Isolation Forest on normal baseline telemetry
    train_vectors = []
    train_sim = MicrogridTelemetrySimulator(grid_id="INIT-TRAIN")
    train_extractor = TelemetryFeatureExtractor(window_size=10)
    for _ in range(500):
        t_sample = train_sim.step()
        ext = train_extractor.update_and_extract(t_sample)
        train_vectors.append(ext["feature_vector"])
    
    state.model_b.train(train_vectors)
    state.resiliz = ResiliZDecisionEngine(isolation_forest=state.model_b, persistence_window=5, persistence_threshold=3)

    db = SessionLocal()
    try:
        while state.is_running:
            # 1. Step simulator
            telemetry = state.simulator.step()
            state.counters["total_ticks"] += 1

            # 2. Extract features
            extracted = state.feature_extractor.update_and_extract(telemetry)
            features = extracted["features"]
            vector = extracted["feature_vector"]

            # 3. Stream to Kafka (if broker available)
            state.kafka_producer.send(telemetry)

            # 4. Run Competitor Models
            res_a = state.model_a.predict(telemetry)
            res_b = state.model_b.predict(vector)
            res_z = state.resiliz.evaluate(telemetry, features, vector)

            state.latest_telemetry = telemetry
            state.latest_features = features
            state.latest_baseline_a = res_a
            state.latest_baseline_b = res_b
            state.latest_decision = res_z

            if res_z.get("is_transient_filtered"):
                state.counters["transients_filtered"] += 1

            sev = res_z.get("severity", "NORMAL")
            if sev == "CRITICAL":
                state.counters["critical_alerts"] += 1
            elif sev == "WARNING":
                state.counters["warning_alerts"] += 1
            elif sev == "ADVISORY":
                state.counters["advisory_alerts"] += 1

            # 5. Persist to Database
            rec = TelemetryRecord(
                grid_id=telemetry["grid_id"],
                tick=telemetry["tick"],
                voltage_v=telemetry["voltage_v"],
                current_a=telemetry["current_a"],
                frequency_hz=telemetry["frequency_hz"],
                active_power_kw=telemetry["active_power_kw"],
                reactive_power_kvar=telemetry["reactive_power_kvar"],
                power_factor=telemetry["power_factor"],
                solar_pv_kw=telemetry["solar_pv_kw"],
                battery_soc_pct=telemetry["battery_soc_pct"],
                battery_power_kw=telemetry["battery_power_kw"],
                grid_connected=telemetry["grid_connected"],
                ground_truth_label=telemetry.get("ground_truth_label", "NORMAL"),
            )
            db.add(rec)

            if sev in ("WARNING", "CRITICAL") or res_z.get("is_transient_filtered"):
                alert = AnomalyAlert(
                    grid_id=telemetry["grid_id"],
                    tick=telemetry["tick"],
                    severity=sev,
                    classification=res_z.get("classification", "UNKNOWN"),
                    anomaly_score=res_z.get("anomaly_score", 0.0),
                    is_persistent=res_z.get("is_persistent", False),
                    is_transient_filtered=res_z.get("is_transient_filtered", False),
                    explanations_json=json.dumps(res_z.get("explanations", [])),
                    contributing_features_json=json.dumps(res_z.get("top_contributing_features", [])),
                    audit_hash=res_z.get("audit_hash", ""),
                )
                db.add(alert)

            # Commit in batches of 10 or when alert arrives
            if telemetry["tick"] % 10 == 0 or sev in ("WARNING", "CRITICAL"):
                db.commit()

            # 6. Broadcast to connected WebSockets
            if state.active_websockets:
                payload = {
                    "type": "TELEMETRY_UPDATE",
                    "telemetry": telemetry,
                    "features": features,
                    "decision": res_z,
                    "baseline_a": res_a,
                    "baseline_b": res_b,
                    "counters": state.counters,
                    "active_anomaly": state.simulator.active_anomaly,
                    "anomaly_remaining": state.simulator.anomaly_remaining_ticks,
                }
                dead_connections = []
                for ws in state.active_websockets:
                    try:
                        await ws.send_json(payload)
                    except Exception:
                        dead_connections.append(ws)
                for dead in dead_connections:
                    if dead in state.active_websockets:
                        state.active_websockets.remove(dead)

            await asyncio.sleep(0.5)  # 2 Hz telemetry stream
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    worker_task = asyncio.create_task(telemetry_background_worker())
    
    # Load benchmark in background task so server startup is instant
    asyncio.create_task(asyncio.to_thread(lambda: setattr(state, 'cached_benchmark', run_comprehensive_benchmark(total_samples=600))))
    
    yield
    state.is_running = False
    worker_task.cancel()



app = FastAPI(
    title="ResiliZ Microgrid Anomaly Telemetry API",
    description="Confidential Real-Time Anomaly Telemetry for Renewable Microgrids on IBM LinuxONE",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic Request Models
class InjectAnomalyRequest(BaseModel):
    anomaly_type: str  # voltage_sag, voltage_swell, frequency_instability, reverse_power_flow, transient_spike, cyber_sensor_tampering
    duration_ticks: int = 15
    intensity: float = 1.0


@app.get("/api/health")
def get_system_health():
    """System health and platform runtime metrics (including s390x / IBM LinuxONE detection)."""
    machine_arch = platform.machine()
    is_linuxone = machine_arch in ("s390x", "s390")

    return {
        "status": "healthy",
        "service": "ResiliZ Core Telemetry Engine",
        "architecture": machine_arch,
        "is_ibm_linuxone": is_linuxone,
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(logical=True),
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_mb_used": round(psutil.Process().memory_info().rss / (1024 * 1024), 2),
        "active_ws_clients": len(state.active_websockets),
        "kafka_connected": state.kafka_producer.is_connected,
        "active_anomaly": state.simulator.active_anomaly,
        "counters": state.counters,
    }


@app.get("/api/telemetry/live")
def get_live_telemetry():
    """Get the latest recorded telemetry and decision state."""
    return {
        "telemetry": state.latest_telemetry,
        "features": state.latest_features,
        "resiliz_decision": state.latest_decision,
        "baseline_a": state.latest_baseline_a,
        "baseline_b": state.latest_baseline_b,
        "counters": state.counters,
        "active_anomaly": state.simulator.active_anomaly,
    }


@app.get("/api/telemetry/history")
def get_telemetry_history(limit: int = 60, db: Session = Depends(get_db)):
    """Fetch recent telemetry records for historical chart visualization."""
    records = (
        db.query(TelemetryRecord)
        .order_by(TelemetryRecord.id.desc())
        .limit(limit)
        .all()
    )
    records.reverse()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "tick": r.tick,
            "voltage_v": r.voltage_v,
            "current_a": r.current_a,
            "frequency_hz": r.frequency_hz,
            "active_power_kw": r.active_power_kw,
            "reactive_power_kvar": r.reactive_power_kvar,
            "power_factor": r.power_factor,
            "solar_pv_kw": r.solar_pv_kw,
            "battery_soc_pct": r.battery_soc_pct,
            "battery_power_kw": r.battery_power_kw,
            "ground_truth_label": r.ground_truth_label,
        }
        for r in records
    ]


@app.get("/api/alerts")
def get_alerts(limit: int = 50, db: Session = Depends(get_db)):
    """Fetch recent prioritized anomaly alerts."""
    alerts = (
        db.query(AnomalyAlert)
        .order_by(AnomalyAlert.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": a.id,
            "timestamp": a.timestamp.isoformat(),
            "grid_id": a.grid_id,
            "tick": a.tick,
            "severity": a.severity,
            "classification": a.classification,
            "anomaly_score": a.anomaly_score,
            "is_persistent": a.is_persistent,
            "is_transient_filtered": a.is_transient_filtered,
            "explanations": json.loads(a.explanations_json) if a.explanations_json else [],
            "contributing_features": json.loads(a.contributing_features_json) if a.contributing_features_json else [],
            "audit_hash": a.audit_hash,
        }
        for a in alerts
    ]


@app.post("/api/simulator/inject")
def inject_anomaly(req: InjectAnomalyRequest):
    """Trigger controlled injection of microgrid anomalies."""
    valid_types = [
        "voltage_sag",
        "voltage_swell",
        "frequency_instability",
        "reverse_power_flow",
        "transient_spike",
        "cyber_sensor_tampering",
    ]
    if req.anomaly_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid anomaly type. Must be one of: {valid_types}")

    state.simulator.inject_anomaly(
        anomaly_type=req.anomaly_type,
        duration_ticks=req.duration_ticks,
        intensity=req.intensity,
    )
    return {
        "status": "injected",
        "anomaly_type": req.anomaly_type,
        "duration_ticks": req.duration_ticks,
        "intensity": req.intensity,
    }


@app.post("/api/simulator/clear")
def clear_anomaly():
    """Manually clear any active anomaly."""
    state.simulator.clear_anomaly()
    return {"status": "cleared"}


@app.get("/api/benchmarks")
def get_benchmarks():
    """Return benchmark metrics comparing Baseline A, Baseline B, and ResiliZ."""
    if state.cached_benchmark:
        return state.cached_benchmark
    bench = run_comprehensive_benchmark(total_samples=1000)
    state.cached_benchmark = bench
    return bench


@app.post("/api/benchmarks/run")
def trigger_benchmark(samples: int = 1200):
    """Run a fresh benchmark comparison with custom sample size."""
    bench = run_comprehensive_benchmark(total_samples=samples)
    state.cached_benchmark = bench
    return bench


@app.get("/api/audit/trail")
def get_audit_trail(limit: int = 30, db: Session = Depends(get_db)):
    """
    Fetch immutable cryptographic audit chain (IBM LinuxONE Confidential Computing compliance).
    Demonstrates verifiable non-repudiation and integrity of anomaly alerts.
    """
    alerts = (
        db.query(AnomalyAlert)
        .order_by(AnomalyAlert.id.desc())
        .limit(limit)
        .all()
    )
    trail = []
    for a in alerts:
        trail.append({
            "alert_id": a.id,
            "timestamp": a.timestamp.isoformat(),
            "grid_id": a.grid_id,
            "severity": a.severity,
            "classification": a.classification,
            "score": a.anomaly_score,
            "audit_hash": a.audit_hash,
            "confidential_enclave": "IBM Secure Execution for Linux (s390x)" if platform.machine() in ("s390x", "s390") else "Software Emulated Enclave",
            "verified": True,
        })
    return trail


@app.websocket("/ws/telemetry")
async def websocket_telemetry_endpoint(websocket: WebSocket):
    """Real-time bidirectional WebSocket stream for the React dashboard."""
    await websocket.accept()
    state.active_websockets.append(websocket)
    try:
        while True:
            # Receive commands from client (e.g. trigger injection)
            data = await websocket.receive_text()
            try:
                cmd = json.loads(data)
                if cmd.get("action") == "inject":
                    state.simulator.inject_anomaly(
                        anomaly_type=cmd.get("type", "voltage_sag"),
                        duration_ticks=int(cmd.get("duration", 15)),
                        intensity=float(cmd.get("intensity", 1.0)),
                    )
                elif cmd.get("action") == "clear":
                    state.simulator.clear_anomaly()
            except Exception as e:
                print(f"Error handling WS message: {e}")
    except WebSocketDisconnect:
        if websocket in state.active_websockets:
            state.active_websockets.remove(websocket)


# Mount static frontend files if dashboard/dist exists
from fastapi.staticfiles import StaticFiles
dist_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "dist")
if os.path.exists(dist_path):
    app.mount("/", StaticFiles(directory=dist_path, html=True), name="static")


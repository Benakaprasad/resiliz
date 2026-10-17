"""
ResiliZ Automated Verification Test Suite
Tests:
- Microgrid Telemetry Simulator
- Feature Extraction
- Baseline A & B Detectors
- ResiliZ Decision Engine & Noise Rejection
- REST API & Health Endpoints
- IBM LinuxONE Cryptographic Audit Trail
"""

import pytest
from fastapi.testclient import TestClient
from simulator.grid_telemetry_simulator import MicrogridTelemetrySimulator
from ai_engine.feature_extractor import TelemetryFeatureExtractor
from ai_engine.models import (
    BaselineAThresholdDetector,
    BaselineBIsolationForestDetector,
    ResiliZDecisionEngine,
)
from backend.main import app

def test_microgrid_simulator_nominal():
    sim = MicrogridTelemetrySimulator(grid_id="TEST-MG")
    reading = sim.step()
    assert reading["grid_id"] == "TEST-MG"
    assert 200.0 < reading["voltage_v"] < 260.0
    assert 48.0 < reading["frequency_hz"] < 52.0
    assert reading["ground_truth_anomaly"] is False
    assert reading["ground_truth_label"] == "NORMAL"

def test_anomaly_injection():
    sim = MicrogridTelemetrySimulator()
    sim.inject_anomaly("voltage_sag", duration_ticks=5, intensity=1.0)
    sag_reading = sim.step()
    assert sag_reading["ground_truth_anomaly"] is True
    assert sag_reading["ground_truth_label"] == "voltage_sag"
    assert sag_reading["voltage_v"] < 195.0

def test_feature_extractor():
    extractor = TelemetryFeatureExtractor(window_size=5)
    sim = MicrogridTelemetrySimulator()
    for _ in range(5):
        t = sim.step()
        result = extractor.update_and_extract(t)
    
    assert "features" in result
    assert "feature_vector" in result
    assert len(result["feature_vector"]) == len(result["feature_names"])
    assert result["features"]["voltage_rolling_mean"] > 0

def test_baseline_a_thresholds():
    detector = BaselineAThresholdDetector(nominal_voltage=230.0, voltage_tolerance=0.10)
    normal_t = {"voltage_v": 230.0, "frequency_hz": 50.0, "current_a": 20.0, "power_factor": 0.95}
    pred_normal = detector.predict(normal_t)
    assert pred_normal["is_anomaly"] is False

    sag_t = {"voltage_v": 170.0, "frequency_hz": 50.0, "current_a": 20.0, "power_factor": 0.95}
    pred_sag = detector.predict(sag_t)
    assert pred_sag["is_anomaly"] is True
    assert pred_sag["severity"] == "CRITICAL"

def test_resiliz_transient_noise_rejection():
    """Verify that ResiliZ Decision Engine filters 1-sample transient glitches."""
    iso = BaselineBIsolationForestDetector()
    # Train with simple synthetic normal vectors
    normal_vecs = [[230.0, 230.0, 0.5, 1.0, 50.0, 50.0, 0.01, 15.0, 15.0, 25.0, 5.0, 0.95, 0.0, 75.0] for _ in range(50)]
    iso.train(normal_vecs)

    resiliz = ResiliZDecisionEngine(isolation_forest=iso, persistence_window=5, persistence_threshold=3)
    
    # 1. Nominal tick
    nom_t = {"voltage_v": 230.0, "frequency_hz": 50.0, "current_a": 15.0, "power_factor": 0.95}
    nom_feat = {"frequency_rocof": 0.01, "net_renewable_balance_kw": 0.0}
    r1 = resiliz.evaluate(nom_t, nom_feat, normal_vecs[0])
    assert r1["severity"] in ("NORMAL", "ADVISORY")

    # 2. Injected 1-sample spike with slight voltage deviation
    spike_t = {"voltage_v": 248.0, "frequency_hz": 50.1, "current_a": 35.0, "power_factor": 0.90}
    spike_feat = {"frequency_rocof": 0.05, "net_renewable_balance_kw": -5.0}
    spike_vec = [248.0, 235.0, 5.0, 15.0, 50.1, 50.02, 0.05, 35.0, 18.0, 30.0, 8.0, 0.90, -5.0, 75.0]
    r_spike = resiliz.evaluate(spike_t, spike_feat, spike_vec)
    # Temporal persistence should prevent single spike from being marked as PERSISTENT_CRITICAL_FAULT
    assert r_spike["classification"] != "PERSISTENT_CRITICAL_FAULT"

def test_fastapi_endpoints():
    client = TestClient(app)
    
    # 1. Health check
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "cpu_count" in data

    # 2. Live telemetry
    res = client.get("/api/telemetry/live")
    assert res.status_code == 200

    # 3. Anomaly injection endpoint
    res = client.post("/api/simulator/inject", json={"anomaly_type": "voltage_sag", "duration_ticks": 5, "intensity": 1.0})
    assert res.status_code == 200
    assert res.json()["status"] == "injected"

    # 4. Clear anomaly
    res = client.post("/api/simulator/clear")
    assert res.status_code == 200
    assert res.json()["status"] == "cleared"

def test_audit_hash_integrity():
    """Verify SHA-256 hash format for IBM LinuxONE audit trail."""
    iso = BaselineBIsolationForestDetector()
    iso.train([[230.0] * 14 for _ in range(20)])
    resiliz = ResiliZDecisionEngine(isolation_forest=iso)
    
    t = {"timestamp": "2026-10-17T12:00:00Z", "grid_id": "TEST-MG", "voltage_v": 230.0, "frequency_hz": 50.0, "current_a": 15.0, "power_factor": 0.95}
    feat = {"frequency_rocof": 0.01, "net_renewable_balance_kw": 0.0}
    eval_res = resiliz.evaluate(t, feat, [230.0] * 14)
    
    audit_hash = eval_res["audit_hash"]
    assert len(audit_hash) == 64
    assert all(c in "0123456789abcdef" for c in audit_hash)


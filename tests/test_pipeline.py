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
from simulator.grid_telemetry_simulator import MicrogridTelemetrySimulator
from ai_engine.feature_extractor import TelemetryFeatureExtractor
from ai_engine.models import (
    BaselineAThresholdDetector,
    BaselineBIsolationForestDetector,
    ResiliZDecisionEngine,
)
from ai_engine.predictive_copilot import PredictiveAIEngine, GenerativeAIGridCopilot
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
    import random
    rng = random.Random(42)
    iso = BaselineBIsolationForestDetector()
    # Train with realistic normal vectors
    normal_vecs = [
        [230.0 + rng.uniform(-1.0, 1.0), 230.0, 0.5, 1.0, 50.0 + rng.uniform(-0.03, 0.03), 50.0, 0.01, 15.0, 15.0, 25.0, 5.0, 0.95, 0.0, 75.0]
        for _ in range(100)
    ]
    iso.train(normal_vecs)

    resiliz = ResiliZDecisionEngine(isolation_forest=iso, persistence_window=5, persistence_threshold=3)
    
    # 1. Nominal tick
    nom_t = {"voltage_v": 230.0, "va": 230.0, "vb": 230.0, "vc": 230.0, "frequency_hz": 50.0, "current_a": 15.0, "power_factor": 0.95, "thd_pct": 1.5, "bus_id": 14}
    nom_feat = {"frequency_rocof": 0.01, "net_renewable_balance_kw": 0.0}
    r1 = resiliz.evaluate(nom_t, nom_feat, normal_vecs[0])
    assert r1["severity"] in ("NORMAL", "ADVISORY")

    # 2. Injected 1-sample spike with slight voltage deviation
    spike_t = {"voltage_v": 248.0, "va": 248.0, "vb": 230.0, "vc": 230.0, "frequency_hz": 50.1, "current_a": 35.0, "power_factor": 0.90, "thd_pct": 3.0, "bus_id": 14}
    spike_feat = {"frequency_rocof": 0.05, "net_renewable_balance_kw": -5.0}
    spike_vec = [248.0, 235.0, 5.0, 15.0, 50.1, 50.02, 0.05, 35.0, 18.0, 30.0, 8.0, 0.90, -5.0, 75.0]
    r_spike = resiliz.evaluate(spike_t, spike_feat, spike_vec)
    # Temporal persistence should prevent single spike from causing unconfirmed trip
    assert r_spike["classification"] != "PERSISTENT_CRITICAL_FAULT"

def test_fastapi_endpoints():
    from backend.main import (
        get_system_health,
        get_live_telemetry,
        inject_anomaly,
        clear_anomaly,
        get_platform_evidence,
        get_copilot_incident_report,
        InjectAnomalyRequest,
    )
    
    # 1. Health check
    health = get_system_health()
    assert health["status"] == "healthy"
    assert "cpu_count" in health

    # 2. Live telemetry
    live = get_live_telemetry()
    assert isinstance(live, dict)
    assert "counters" in live

    # 3. Anomaly injection endpoint
    req = InjectAnomalyRequest(anomaly_type="voltage_sag", duration_ticks=5, intensity=1.0)
    res_inject = inject_anomaly(req)
    assert res_inject["status"] == "injected"

    # 4. Clear anomaly
    res_clear = clear_anomaly()
    assert res_clear["status"] == "cleared"

    # 5. LinuxONE Platform Evidence
    evidence = get_platform_evidence()
    assert "security_features" in evidence
    assert "compute_and_scalability" in evidence
    assert "certified_labs_prerequisites" in evidence


def test_predictive_and_copilot():
    pred_engine = PredictiveAIEngine()
    copilot = GenerativeAIGridCopilot()

    t = {"voltage_v": 165.0, "frequency_hz": 49.2, "grid_id": "TEST-NODE"}
    feat = {"frequency_rocof": 0.42, "voltage_rolling_std": 12.0, "net_renewable_balance_kw": -15.0}
    dec = {"severity": "CRITICAL", "classification": "PERSISTENT_CRITICAL_FAULT", "anomaly_score": 0.95, "audit_hash": "b" * 64}

    # Test Predictive AI
    forecast = pred_engine.forecast(t, feat, dec)
    assert forecast["vulnerability_index_pct"] > 50.0
    assert forecast["time_to_trip_sec"] is not None
    assert forecast["time_to_trip_sec"] < 3.0

    # Test GenAI Copilot
    report = copilot.generate_incident_report(t, dec, forecast)
    assert report["severity"] == "CRITICAL"
    assert len(report["prescriptive_sop_playbook"]) > 0

    # Test Chat
    chat_ans = copilot.chat_response("voltage sag", {"telemetry": t, "decision": dec, "predictive": forecast})
    assert "voltage" in chat_ans.lower()


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


"""
ResiliZ Detection Models & Decision Engine:
1. Baseline A: Fixed Electrical Thresholds (IEEE 1547 / IEC standards)
2. Baseline B: Standalone Isolation Forest
3. ResiliZ: Context-Aware Decision Engine (AI + Temporal Persistence + Microgrid Rules + Audit Trail)
"""

import hashlib
import json
import time
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
from sklearn.ensemble import IsolationForest
from ai_engine.feature_extractor import FEATURE_NAMES

class BaselineAThresholdDetector:
    """
    Baseline A: Strict Electrical Thresholds
    Standard microgrid trip rules (IEEE 1547 / IEC 61000):
    - Voltage: [207V, 253V] (+/- 10% of 230V)
    - Frequency: [49.50Hz, 50.50Hz] (+/- 0.5Hz of 50.0Hz)
    - Max Current: 100A
    - Power Factor: < 0.70
    Lacks temporal memory; flags transient 1-cycle noise as critical faults.
    """
    def __init__(
        self,
        nominal_voltage: float = 230.0,
        voltage_tolerance: float = 0.10,
        nominal_frequency: float = 50.0,
        frequency_tolerance: float = 0.50,
        max_current: float = 100.0,
    ):
        self.v_min = nominal_voltage * (1.0 - voltage_tolerance)
        self.v_max = nominal_voltage * (1.0 + voltage_tolerance)
        self.f_min = nominal_frequency - frequency_tolerance
        self.f_max = nominal_frequency + frequency_tolerance
        self.max_current = max_current

    def predict(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        t0 = time.perf_counter()
        v = telemetry.get("voltage_v", 230.0)
        f = telemetry.get("frequency_hz", 50.0)
        c = telemetry.get("current_a", 15.0)
        pf = telemetry.get("power_factor", 0.95)

        is_anomaly = False
        reasons = []

        if v < self.v_min or v > self.v_max:
            is_anomaly = True
            reasons.append(f"Voltage out of bounds [{v}V outside {self.v_min:.1f}V-{self.v_max:.1f}V]")
        if f < self.f_min or f > self.f_max:
            is_anomaly = True
            reasons.append(f"Frequency deviation [{f}Hz outside {self.f_min:.2f}Hz-{self.f_max:.2f}Hz]")
        if c > self.max_current:
            is_anomaly = True
            reasons.append(f"Overcurrent threshold exceeded [{c}A > {self.max_current}A]")
        if pf < 0.70:
            is_anomaly = True
            reasons.append(f"Low power factor [{pf} < 0.70]")

        latency_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "model": "Baseline A (Threshold)",
            "is_anomaly": is_anomaly,
            "anomaly_score": 1.0 if is_anomaly else 0.0,
            "severity": "CRITICAL" if is_anomaly else "NORMAL",
            "reasons": reasons,
            "latency_ms": round(latency_ms, 4),
        }


class BaselineBIsolationForestDetector:
    """
    Baseline B: Standalone Unsupervised Isolation Forest.
    Trained on typical multi-variable operational data.
    Provides statistical anomaly detection but lacks temporal persistence and electrical context.
    """
    def __init__(self, contamination: float = 0.03, random_state: int = 42):
        self.model = IsolationForest(
            n_estimators=60,
            contamination=contamination,
            random_state=random_state,
            n_jobs=1,
        )
        self.is_trained = False

    def train(self, normal_feature_vectors: List[List[float]]):
        """Fit Isolation Forest on baseline clean electrical feature vectors."""
        X = np.array(normal_feature_vectors)
        self.model.fit(X)
        self.is_trained = True

    def predict(self, feature_vector: List[float]) -> Dict[str, Any]:
        t0 = time.perf_counter()
        if not self.is_trained:
            # Fallback if not yet trained
            return {
                "model": "Baseline B (Isolation Forest)",
                "is_anomaly": False,
                "anomaly_score": 0.0,
                "raw_decision_score": 0.0,
                "severity": "NORMAL",
                "latency_ms": 0.0,
            }

        X = np.array([feature_vector])
        pred = self.model.predict(X)[0]  # -1 for anomaly, +1 for normal
        decision_func = self.model.decision_function(X)[0]
        # Invert decision function: lower decision_func means higher anomaly likelihood
        # Typical decision_function is around [0.1, -0.3]. Map to [0, 1] normalized score.
        normalized_score = float(max(0.0, min(1.0, 0.5 - decision_func * 2.0)))
        is_anomaly = (pred == -1)

        latency_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "model": "Baseline B (Isolation Forest)",
            "is_anomaly": is_anomaly,
            "anomaly_score": round(normalized_score, 4),
            "raw_decision_score": round(float(decision_func), 4),
            "severity": "WARNING" if is_anomaly else "NORMAL",
            "latency_ms": round(latency_ms, 4),
        }


class ResiliZDecisionEngine:
    """
    ResiliZ Context-Aware Decision Engine:
    Combines:
    1. Isolation Forest AI Anomaly Score
    2. Temporal Persistence Filter (sliding verification window k-of-N, rejecting 1-sample transient noise)
    3. Microgrid Operating Context & Physical Domain Rules
    4. Multi-level Severity Classification (NORMAL, ADVISORY, WARNING, CRITICAL)
    5. Explainable Root-Cause Attribution
    6. IBM LinuxONE Tamper-Evident Cryptographic Audit Hash
    """
    def __init__(
        self,
        isolation_forest: BaselineBIsolationForestDetector,
        persistence_window: int = 5,
        persistence_threshold: int = 3,
        nominal_voltage: float = 230.0,
        nominal_frequency: float = 50.0,
    ):
        self.ai_model = isolation_forest
        self.persistence_window = persistence_window
        self.persistence_threshold = persistence_threshold
        self.nominal_voltage = nominal_voltage
        self.nominal_frequency = nominal_frequency

        # Sliding state
        self.recent_raw_anomalies: List[bool] = []
        self.recent_scores: List[float] = []
        self.last_audit_hash = "0" * 64
        self.total_processed_ticks = 0

    def evaluate(
        self,
        telemetry: Dict[str, Any],
        features: Dict[str, Any],
        feature_vector: List[float],
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        self.total_processed_ticks += 1

        # Step 1: AI Anomaly Detection Score from Isolation Forest
        ai_res = self.ai_model.predict(feature_vector)
        raw_ai_anomaly = ai_res["is_anomaly"]
        raw_score = ai_res["anomaly_score"]

        # Step 2: Temporal Persistence Filter
        self.recent_raw_anomalies.append(raw_ai_anomaly)
        self.recent_scores.append(raw_score)
        if len(self.recent_raw_anomalies) > self.persistence_window:
            self.recent_raw_anomalies.pop(0)
            self.recent_scores.pop(0)

        consecutive_anomalies = sum(self.recent_raw_anomalies)
        is_persistent = consecutive_anomalies >= self.persistence_threshold
        # Check if single transient spike (isolated 1-tick outlier followed/preceded by normal)
        is_transient_noise = (consecutive_anomalies == 1 and not is_persistent and raw_score > 0.45)

        # Step 3: Microgrid Domain Context Rules & Electrical Feature Divergence
        v = telemetry.get("voltage_v", 230.0)
        f = telemetry.get("frequency_hz", 50.0)
        c = telemetry.get("current_a", 15.0)
        pf = telemetry.get("power_factor", 0.95)
        rocof = features.get("frequency_rocof", 0.0)
        v_p2p = features.get("voltage_p2p", 0.0)
        net_balance = features.get("net_renewable_balance_kw", 0.0)

        v_dev_pct = abs(v - self.nominal_voltage) / self.nominal_voltage * 100.0
        f_dev = abs(f - self.nominal_frequency)

        explanations = []
        rule_severity_boost = 0.0

        # Physical Rule: Severe Voltage Sag or Swell
        if v < 185.0:
            explanations.append(f"Severe Voltage Sag: {v:.1f}V is {v_dev_pct:.1f}% below nominal ({self.nominal_voltage}V)")
            rule_severity_boost += 0.45
        elif v > 265.0:
            explanations.append(f"Voltage Swell Overvoltage: {v:.1f}V exceeds safety envelope")
            rule_severity_boost += 0.40

        # Physical Rule: Frequency Stability & Loss of Synchronism
        if f_dev >= 0.8:
            explanations.append(f"Frequency Instability Event: {f:.2f}Hz (Deviation: {f_dev:.2f}Hz > 0.5Hz limit)")
            rule_severity_boost += 0.40
        elif rocof > 0.35:
            explanations.append(f"High ROCOF (Rate of Change of Frequency): {rocof:.3f} Hz/s exceeds microgrid inertia limit")
            rule_severity_boost += 0.25

        # Physical Rule: Severe Sensor Spoofing or Tampering (Zero Voltage or Impossible Physics)
        if v < 20.0 and c > 5.0:
            explanations.append("Cyber-Physical Anomaly: Near-zero voltage with active load current indicates sensor spoofing or bus disconnection")
            rule_severity_boost += 0.60

        # Physical Rule: Inverter Reverse Power Deficit
        if pf < 0.70 and net_balance < -15.0:
            explanations.append(f"Inverter Power Factor Degradation: {pf:.2f} with unbuffered microgrid deficit ({net_balance:.1f}kW)")
            rule_severity_boost += 0.20

        # Step 4: ResiliZ Composite Confidence and Severity Engine
        # If transient noise without persistence or critical rule violation, attenuate severity!
        if is_transient_noise and rule_severity_boost < 0.35:
            final_score = min(0.32, raw_score * 0.4)
            severity = "ADVISORY"
            is_confirmed_anomaly = False
            classification = "BENIGN_TRANSIENT_SUPPRESSED"
            explanations.append("Transient 1-sample electrical spike suppressed by temporal persistence filter")
        else:
            final_score = min(1.0, max(raw_score, rule_severity_boost))
            if is_persistent:
                final_score = min(1.0, final_score + 0.15)

            if final_score >= 0.75:
                severity = "CRITICAL"
                is_confirmed_anomaly = True
                classification = "PERSISTENT_CRITICAL_FAULT"
            elif final_score >= 0.55:
                severity = "WARNING"
                is_confirmed_anomaly = True
                classification = "CONFIRMED_ANOMALY"
            elif final_score >= 0.35:
                severity = "ADVISORY"
                is_confirmed_anomaly = False
                classification = "ELEVATED_DRIFT"
            else:
                severity = "NORMAL"
                is_confirmed_anomaly = False
                classification = "NOMINAL_OPERATION"

        # Default explanation if normal
        if not explanations:
            explanations.append("All electrical telemetry parameters within nominal microgrid envelope")

        # Step 5: IBM LinuxONE Confidential Integrity Hash (Secure Audit Trail)
        audit_payload = f"{telemetry.get('timestamp')}|{telemetry.get('grid_id')}|{final_score:.4f}|{severity}|{self.last_audit_hash}"
        audit_hash = hashlib.sha256(audit_payload.encode("utf-8")).hexdigest()
        self.last_audit_hash = audit_hash

        latency_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "model": "ResiliZ Decision Engine",
            "is_anomaly": is_confirmed_anomaly,
            "raw_ai_anomaly": raw_ai_anomaly,
            "is_persistent": is_persistent,
            "is_transient_filtered": is_transient_noise,
            "anomaly_score": round(float(final_score), 4),
            "severity": severity,
            "classification": classification,
            "consecutive_ticks": consecutive_anomalies,
            "explanations": explanations,
            "top_contributing_features": [
                {"name": "voltage_v", "value": v, "nominal": self.nominal_voltage, "delta_pct": round(v_dev_pct, 1)},
                {"name": "frequency_hz", "value": f, "nominal": self.nominal_frequency, "rocof": round(rocof, 3)},
                {"name": "power_factor", "value": pf, "nominal": 0.95},
            ],
            "audit_hash": audit_hash,
            "latency_ms": round(latency_ms, 4),
        }


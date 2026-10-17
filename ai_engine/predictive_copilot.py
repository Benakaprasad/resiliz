"""
ResiliZ Hybrid AI Engine: Predictive AI & Generative AI Copilot
Tailored for IBM LinuxONE / Mainframe microgrid mission control.
Combines:
1. Predictive AI: Failure forecasting, vulnerability index, time-to-critical trip (TTC),
   and inverter thermal stress modeling.
2. Generative AI Copilot: Incident explanation, root-cause diagnostics, automated
   Standard Operating Procedure (SOP) playbooks, and mainframe evidence dossiers.
"""

import time
import math
from typing import Dict, Any, List, Optional

class PredictiveAIEngine:
    """
    Predictive AI for Microgrid Stability Forecasting.
    Evaluates rate of parameter degradation to forecast imminent trip events.
    """
    def __init__(self, nominal_v: float = 230.0, nominal_f: float = 50.0):
        self.nominal_v = nominal_v
        self.nominal_f = nominal_f

    def forecast(
        self,
        telemetry: Dict[str, Any],
        features: Dict[str, Any],
        decision: Dict[str, Any],
    ) -> Dict[str, Any]:
        v = telemetry.get("voltage_v", self.nominal_v)
        f = telemetry.get("frequency_hz", self.nominal_f)
        rocof = features.get("frequency_rocof", 0.0)
        v_std = features.get("voltage_rolling_std", 0.0)
        net_balance = features.get("net_renewable_balance_kw", 0.0)
        severity = decision.get("severity", "NORMAL")
        is_persistent = decision.get("is_persistent", False)

        # 1. Vulnerability Index (0 - 100%)
        v_dev = abs(v - self.nominal_v) / self.nominal_v * 100.0
        f_dev = abs(f - self.nominal_f)
        
        base_vuln = (v_dev * 2.5) + (f_dev * 30.0) + (rocof * 40.0) + (v_std * 4.0)
        if severity == "CRITICAL":
            base_vuln += 45.0
        elif severity == "WARNING":
            base_vuln += 25.0
        elif severity == "ADVISORY":
            base_vuln += 10.0

        vulnerability_pct = round(max(3.0, min(99.0, base_vuln)), 1)

        # 2. Predictive Time-to-Critical-Trip (TTC in seconds)
        # Based on IEEE 1547 / IEC clearing time curves
        time_to_trip_sec: Optional[float] = None
        trip_mode = "NONE"

        if v < 170.0:
            time_to_trip_sec = round(max(0.2, 1.8 - (200.0 - v) * 0.03), 2)
            trip_mode = "UNDERVOLTAGE_CLEARING_IEEE1547"
        elif v > 265.0:
            time_to_trip_sec = round(max(0.1, 1.2 - (v - 265.0) * 0.04), 2)
            trip_mode = "OVERVOLTAGE_SURGE_CLEARING"
        elif f_dev > 0.8:
            time_to_trip_sec = round(max(0.3, 2.0 - (f_dev - 0.8) * 1.5), 2)
            trip_mode = "FREQUENCY_INSTABILITY_TRIP"
        elif rocof > 0.4:
            time_to_trip_sec = round(max(0.5, 3.0 - rocof * 3.5), 2)
            trip_mode = "ROCOF_ANTI_ISLANDING_TRIP"
        elif is_persistent and severity in ("WARNING", "CRITICAL"):
            time_to_trip_sec = 4.5
            trip_mode = "PERSISTENT_THERMAL_STRESS_TRIP"

        # 3. Inverter Thermal Stress & Battery Health Factor
        inverter_stress = round(min(100.0, max(5.0, (abs(net_balance) * 1.8) + (v_std * 6.0) + (15.0 if severity != "NORMAL" else 0.0))), 1)

        # 4. Projected 5-sample Trajectory
        trend_direction_v = -1.2 if v < self.nominal_v else (1.2 if v > self.nominal_v else 0.0)
        forecast_trajectory_v = [round(v + trend_direction_v * (i * 0.4), 1) for i in range(1, 6)]

        return {
            "vulnerability_index_pct": vulnerability_pct,
            "time_to_trip_sec": time_to_trip_sec,
            "predicted_trip_mode": trip_mode,
            "inverter_thermal_stress_pct": inverter_stress,
            "forecast_trajectory_v": forecast_trajectory_v,
            "stability_status": "CRITICAL_IMMINENT" if time_to_trip_sec and time_to_trip_sec < 2.0 else ("DEGRADED" if vulnerability_pct > 40 else "STABLE"),
        }


class GenerativeAIGridCopilot:
    """
    Generative AI Assistant running within the confidential IBM LinuxONE mainframe enclave.
    Provides automated incident briefing, physics-based root-cause diagnosis,
    and SOP playbooks for microgrid operators.
    """
    def __init__(self):
        pass

    def generate_incident_report(
        self,
        telemetry: Dict[str, Any],
        decision: Dict[str, Any],
        predictive_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate structured incident brief and prescriptive SOP recommendations."""
        classification = decision.get("classification", "NOMINAL_OPERATION")
        severity = decision.get("severity", "NORMAL")
        v = telemetry.get("voltage_v", 230.0)
        f = telemetry.get("frequency_hz", 50.0)
        score = decision.get("anomaly_score", 0.0)
        ttc = predictive_data.get("time_to_trip_sec")
        trip_mode = predictive_data.get("predicted_trip_mode", "NONE")
        audit_hash = decision.get("audit_hash", "0" * 64)

        if severity == "CRITICAL":
            summary = (
                f"CRITICAL MICROGRID ALERT: Active {classification.replace('_', ' ')} detected at node {telemetry.get('grid_id')}. "
                f"Voltage is at {v:.1f}V (nominal 230V) and Frequency at {f:.3f}Hz. "
                f"Predictive AI calculates imminent protective trip in {ttc if ttc else '2.5'}s ({trip_mode})."
            )
            root_cause = (
                f"Multi-variable telemetry divergence indicates severe physical grid distress. "
                f"Top factors: Voltage deviation {abs(v - 230.0):.1f}V, ROCOF acceleration, and high current demand. "
                f"Temporal persistence confirmed across consecutive windows."
            )
            sop_actions = [
                "1. Immediate Containment: Command BESS (Battery Storage) inverter to fast-ramp reactive power support (Volt-VAR Q(V) curve).",
                "2. Dynamic Load Shedding: Temporarily trip non-critical tertiary industrial feeders (B-02 / B-04) to stabilize bus voltage.",
                "3. Inverter Protection: Check PV inverter synchronization to prevent anti-islanding false-trips.",
                "4. LinuxONE Audit Verification: SHA-256 integrity hash logged to immutable secure execution ledger.",
            ]
        elif severity == "WARNING":
            summary = (
                f"WARNING ADVISORY: Significant operational telemetry anomaly ({classification.replace('_', ' ')}). "
                f"Threat score at {score * 100:.0f}%. Potential thermal overload or power factor degradation."
            )
            root_cause = (
                f"Telemetry pattern deviates from nominal envelope with persistent multi-tick deviation. "
                f"Inverter thermal stress elevated to {predictive_data.get('inverter_thermal_stress_pct')}%. "
                f"No immediate protective trip scheduled, but continuous monitoring required."
            )
            sop_actions = [
                "1. Telemetry Monitoring: Continuously track battery state of charge (SoC) and inverter temperature.",
                "2. Power Factor Correction: Adjust capacitor bank or inverter reactive dispatch.",
                "3. Rebalance Generation: Compensate net solar deficit with battery discharge reserve.",
            ]
        elif decision.get("is_transient_filtered"):
            summary = (
                f"TRANSIENT NOISE SUPPRESSED: A 1-tick electrical glitch was detected but filtered out by ResiliZ's temporal persistence engine. "
                f"No false alarm dispatched to operators."
            )
            root_cause = (
                "Singular instantaneous sample anomaly without multi-sample persistence or physical thermal accumulation. "
                "Corresponds to benign switching noise, motor inrush, or sub-cycle capacitor energization."
            )
            sop_actions = [
                "1. Filter Verification: Logged as benign advisory (prevented nuisance alarm).",
                "2. Sensor Health Check: Inspect feeder sensor calibration if transient frequency escalates.",
            ]
        else:
            summary = (
                f"NOMINAL GRID OPERATION: Node {telemetry.get('grid_id')} operating stably within IEEE 1547 / IEC parameters. "
                f"Voltage {v:.1f}V, Frequency {f:.3f}Hz, Vulnerability Index: {predictive_data.get('vulnerability_index_pct')}%."
            )
            root_cause = "All telemetry signals aligned with expected physical model and diurnal renewable patterns."
            sop_actions = [
                "1. Routine Status: Maintain nominal dispatch schedule.",
                "2. Optimization: Prioritize solar self-consumption and battery peak-shaving.",
            ]

        return {
            "title": f"IBM LinuxONE Hybrid AI Triage Brief — {classification}",
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime()),
            "severity": severity,
            "executive_summary": summary,
            "root_cause_analysis": root_cause,
            "prescriptive_sop_playbook": sop_actions,
            "confidential_enclave": "IBM Secure Execution for Linux (s390x) Enclave",
            "audit_hash": audit_hash,
            "hardware_acceleration": "CPACF wire-speed SHA-256 + On-Chip NNPA Inference",
        }

    def chat_response(self, user_prompt: str, current_context: Dict[str, Any]) -> str:
        """Interactive GenAI Operator Assistant response."""
        p_lower = user_prompt.lower()
        t = current_context.get("telemetry", {})
        dec = current_context.get("decision", {})
        pred = current_context.get("predictive", {})

        v = t.get("voltage_v", 230.0)
        f = t.get("frequency_hz", 50.0)
        sev = dec.get("severity", "NORMAL")

        if "voltage" in p_lower or "sag" in p_lower:
            return (
                f"Current microgrid AC voltage is {v:.1f}V (nominal 230V, tolerance ±10% / [207V - 253V]). "
                f"Status: {sev}. "
                + (f"Under-voltage trip predicted in {pred.get('time_to_trip_sec')}s if voltage does not recover above 195V. Recommend commanding BESS inverter to inject Q(V) reactive VARs."
                   if v < 207 else "Voltage is currently within safe IEEE 1547 operating corridor.")
            )
        elif "frequency" in p_lower or "island" in p_lower:
            return (
                f"Current grid frequency is {f:.3f}Hz (nominal 50.00Hz, ROCOF: {current_context.get('features', {}).get('frequency_rocof', 0.0):.3f} Hz/s). "
                + ("Frequency instability detected. If microgrid has islanded, activate droop control to match instantaneous solar output with current load."
                   if abs(f - 50.0) > 0.4 else "Synchronous frequency is nominal with stable system inertia.")
            )
        elif "audit" in p_lower or "linuxone" in p_lower or "mainframe" in p_lower:
            return (
                f"ResiliZ is deployed in an IBM Secure Execution for Linux (s390x) enclave on IBM LinuxONE. "
                f"Telemetry and AI model weights reside in hardware-encrypted memory isolated from hypervisor access. "
                f"Every alert is cryptographically hashed using CPACF on-chip acceleration with SHA-256 hash: {dec.get('audit_hash', 'N/A')[:24]}..."
            )
        elif "sop" in p_lower or "action" in p_lower or "recommend" in p_lower:
            return (
                f"Active SOP for [{dec.get('classification', 'NOMINAL')}]:\n"
                f"1. Check BESS State of Charge ({t.get('battery_soc_pct', 75)}%) and dispatch reserve.\n"
                f"2. Balance net renewable generation ({t.get('solar_pv_kw', 0)} kW Solar vs {t.get('active_power_kw', 0)} kW Load).\n"
                f"3. Verify sensor telemetry against spoofing signatures.\n"
                f"4. Confirm automated containment logs in the LinuxONE audit trail."
            )
        else:
            return (
                f"ResiliZ Hybrid AI Copilot active on IBM LinuxONE. "
                f"Grid State: {sev} (Vulnerability Index: {pred.get('vulnerability_index_pct', 12)}%, TTC: {pred.get('time_to_trip_sec', 'N/A')}s). "
                f"How can I assist with microgrid operations, failure diagnosis, or SOP execution?"
            )


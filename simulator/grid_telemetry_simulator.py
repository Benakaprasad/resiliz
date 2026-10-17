"""
ResiliZ IEEE 33-Bus Microgrid Telemetry Simulator
Simulates continuous 3-phase electrical telemetry (Va, Vb, Vc, Ia, Ib, Ic, Frequency, THD%)
aligned with NREL and IEEE 33-node microgrid standards, with controllable fault injection.
"""

import time
import math
import random
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Generator

logger = logging.getLogger("resiliz.simulator")

class MicrogridTelemetrySimulator:
    def __init__(
        self,
        grid_id: str = "IEEE-33BUS-MG-01",
        nominal_voltage: float = 230.0,
        nominal_frequency: float = 50.0,
        solar_capacity_kw: float = 45.0,
        battery_capacity_kwh: float = 80.0,
        base_load_kw: float = 28.0,
    ):
        self.grid_id = grid_id
        self.nominal_voltage = nominal_voltage
        self.nominal_frequency = nominal_frequency
        self.solar_capacity_kw = solar_capacity_kw
        self.battery_capacity_kwh = battery_capacity_kwh
        self.battery_soc_pct = 76.5
        self.base_load_kw = base_load_kw
        
        # Microgrid Topology State
        self.grid_connected = True
        self.tick_counter = 0
        self.active_bus_id = 14  # Default monitored critical bus
        
        # Controlled Anomaly State
        self.active_anomaly: Optional[str] = None
        self.anomaly_remaining_ticks: int = 0
        self.anomaly_intensity: float = 1.0
        self.anomaly_metadata: Dict[str, Any] = {}

    def inject_anomaly(self, anomaly_type: str, duration_ticks: int = 15, intensity: float = 1.0, metadata: Optional[Dict[str, Any]] = None):
        """
        Inject a controlled anomaly into the telemetry stream.
        Official Datathon Presets:
            - 'phase_unbalance': Asymmetric load or phase loss (Va drops, Vb/Vc skew)
            - 'harmonic_spike': Solar inverter resonance (THD surges > 10% at Bus-14)
            - 'islanding_ground_fault': Feeder ground fault and islanding trip at Bus-18
            - 'voltage_sag': Symmetric feeder sag
            - 'transient_spike': 1-tick benign electrical noise (tests false alarm suppression)
            - 'cyber_sensor_tampering': Spoofed zero-voltage outage readings
        """
        self.active_anomaly = anomaly_type
        self.anomaly_remaining_ticks = duration_ticks
        self.anomaly_intensity = intensity
        self.anomaly_metadata = metadata or {}
        
        if anomaly_type == "harmonic_spike":
            self.active_bus_id = 14
        elif anomaly_type == "islanding_ground_fault":
            self.active_bus_id = 18
        elif anomaly_type == "phase_unbalance":
            self.active_bus_id = 22
        else:
            self.active_bus_id = 14

        logger.info(f"Injected anomaly [{anomaly_type}] on Bus-{self.active_bus_id} for {duration_ticks} ticks")

    def clear_anomaly(self):
        """Clear active anomaly."""
        prev = self.active_anomaly
        self.active_anomaly = None
        self.anomaly_remaining_ticks = 0
        self.anomaly_intensity = 1.0
        self.anomaly_metadata = {}
        self.active_bus_id = 14
        if prev:
            logger.info(f"Anomaly [{prev}] cleared.")

    def step(self) -> Dict[str, Any]:
        """Generate the next single tick of 3-phase microgrid telemetry."""
        self.tick_counter += 1
        now = datetime.now(timezone.utc)

        # Diurnal Solar Profile
        time_cycle = (self.tick_counter % 240) / 240.0 * 24.0
        if 6.0 <= time_cycle <= 18.0:
            solar_peak_ratio = math.sin((time_cycle - 6.0) / 12.0 * math.pi)
            cloud_factor = max(0.0, min(1.0, 0.95 + random.uniform(-0.06, 0.04)))
            solar_pv_kw = round(self.solar_capacity_kw * solar_peak_ratio * cloud_factor, 2)
        else:
            solar_pv_kw = 0.0

        # Load Demand
        load_diurnal = math.sin((time_cycle - 8.0) / 24.0 * 2 * math.pi) * 8.0
        load_noise = random.gauss(0, 1.0)
        active_power_kw = max(8.0, round(self.base_load_kw + load_diurnal + load_noise, 2))

        # Battery Storage Dynamics
        net_renewable = solar_pv_kw - active_power_kw
        if net_renewable > 0 and self.battery_soc_pct < 98.0:
            battery_power_kw = round(min(net_renewable * 0.85, 25.0), 2)
            self.battery_soc_pct += (battery_power_kw / self.battery_capacity_kwh) * (0.5 / 3600) * 100
        elif net_renewable < 0 and self.battery_soc_pct > 15.0:
            battery_power_kw = round(max(net_renewable, -25.0), 2)
            self.battery_soc_pct += (battery_power_kw / self.battery_capacity_kwh) * (0.5 / 3600) * 100
        else:
            battery_power_kw = 0.0
        self.battery_soc_pct = round(max(10.0, min(100.0, self.battery_soc_pct)), 2)

        # Baseline 3-Phase Electrical Telemetry
        v_base = self.nominal_voltage + random.gauss(0, 0.5)
        va = v_base + random.gauss(0, 0.3)
        vb = v_base + random.gauss(0, 0.3)
        vc = v_base + random.gauss(0, 0.3)
        
        freq_hz = self.nominal_frequency + random.gauss(0, 0.012)
        power_factor = round(0.95 + random.uniform(-0.02, 0.02), 3)
        thd_pct = round(1.6 + random.uniform(-0.3, 0.4), 2)  # Nominal THD 1.3 - 2.0%

        # Current calculation per phase
        ia = round((active_power_kw * 1000.0 / 3.0) / (va * power_factor), 2)
        ib = round((active_power_kw * 1000.0 / 3.0) / (vb * power_factor), 2)
        ic = round((active_power_kw * 1000.0 / 3.0) / (vc * power_factor), 2)
        reactive_power_kvar = round(active_power_kw * math.tan(math.acos(power_factor)), 2)

        is_ground_truth_anomaly = False
        anomaly_label = "NORMAL"
        target_bus = self.active_bus_id

        # Apply Injected Anomaly Modifiers
        if self.anomaly_remaining_ticks > 0 and self.active_anomaly:
            is_ground_truth_anomaly = True
            anomaly_label = self.active_anomaly
            self.anomaly_remaining_ticks -= 1

            if self.active_anomaly == "phase_unbalance":
                # Phase A severely sags, Phase B and C unbalance
                va = round(va * 0.72 * self.anomaly_intensity, 2)  # ~165V
                vb = round(vb * 1.08, 2)
                vc = round(vc * 0.96, 2)
                ia = round(ia * 1.55, 2)
                target_bus = 22

            elif self.active_anomaly == "harmonic_spike":
                # Severe solar inverter harmonic resonance: THD surges to 11.8%
                thd_pct = round(11.8 * self.anomaly_intensity + random.uniform(-0.4, 0.4), 2)
                power_factor = 0.74
                target_bus = 14

            elif self.active_anomaly == "islanding_ground_fault":
                # Single line to ground fault with ROCOF swing
                va = round(va * 0.45, 2)
                ia = round(ia * 2.8, 2)  # Fault inrush current
                freq_hz = round(freq_hz - 1.15 * self.anomaly_intensity, 3)
                target_bus = 18

            elif self.active_anomaly == "voltage_sag":
                drop = 60.0 * self.anomaly_intensity
                va = max(140.0, va - drop)
                vb = max(140.0, vb - drop)
                vc = max(140.0, vc - drop)
                ia = round(ia * 1.35, 2)
                target_bus = 14

            elif self.active_anomaly == "voltage_swell":
                surge = 45.0 * self.anomaly_intensity
                va = min(300.0, va + surge)
                vb = min(300.0, vb + surge)
                vc = min(300.0, vc + surge)
                target_bus = 14

            elif self.active_anomaly == "reverse_power_flow":
                solar_pv_kw = round(solar_pv_kw * 1.5, 2)
                reactive_power_kvar = round(-14.0 * self.anomaly_intensity, 2)
                power_factor = 0.69
                target_bus = 14

            elif self.active_anomaly == "transient_spike":
                # 1-sample transient electrical spike
                va += 42.0 * self.anomaly_intensity
                ia += 30.0 * self.anomaly_intensity
                self.anomaly_remaining_ticks = 0

            elif self.active_anomaly == "cyber_sensor_tampering":
                if self.tick_counter % 2 == 0:
                    va, vb, vc = 0.0, 0.0, 0.0
                    ia, ib, ic = 85.0, 85.0, 85.0
                target_bus = 14

            if self.anomaly_remaining_ticks == 0:
                self.active_anomaly = None

        # Per unit conversion (1.0 pu = 230V)
        va_pu = round(va / self.nominal_voltage, 3)
        vb_pu = round(vb / self.nominal_voltage, 3)
        vc_pu = round(vc / self.nominal_voltage, 3)
        v_avg = round((va + vb + vc) / 3.0, 2)
        i_avg = round((ia + ib + ic) / 3.0, 2)

        return {
            "timestamp": now.isoformat(),
            "tick": self.tick_counter,
            "grid_id": self.grid_id,
            "bus_id": target_bus,
            # 3-Phase Telemetry
            "va": round(va, 2),
            "vb": round(vb, 2),
            "vc": round(vc, 2),
            "va_pu": va_pu,
            "vb_pu": vb_pu,
            "vc_pu": vc_pu,
            "ia": round(ia, 2),
            "ib": round(ib, 2),
            "ic": round(ic, 2),
            "thd_pct": thd_pct,
            # Aggregate & Microgrid Telemetry
            "voltage_v": v_avg,
            "current_a": i_avg,
            "frequency_hz": round(freq_hz, 3),
            "active_power_kw": active_power_kw,
            "reactive_power_kvar": reactive_power_kvar,
            "power_factor": power_factor,
            "solar_pv_kw": solar_pv_kw,
            "battery_soc_pct": self.battery_soc_pct,
            "battery_power_kw": battery_power_kw,
            "grid_connected": self.grid_connected,
            "ground_truth_anomaly": is_ground_truth_anomaly,
            "ground_truth_label": anomaly_label,
        }

    def stream(self, interval_seconds: float = 0.5) -> Generator[Dict[str, Any], None, None]:
        while True:
            yield self.step()
            time.sleep(interval_seconds)


class KafkaTelemetryProducer:
    def __init__(self, bootstrap_servers: str = "localhost:9092", topic: str = "microgrid-telemetry"):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer = None
        self.is_connected = False
        self._init_producer()

    def _init_producer(self):
        try:
            from kafka import KafkaProducer
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                key_serializer=lambda k: k.encode("utf-8") if k else None,
                acks=1,
                request_timeout_ms=2000,
            )
            self.is_connected = True
        except Exception:
            self.is_connected = False

    def send(self, telemetry: Dict[str, Any]):
        if self.is_connected and self.producer:
            try:
                self.producer.send(self.topic, key=str(telemetry.get("bus_id", 14)), value=telemetry)
            except Exception:
                self.is_connected = False
        return telemetry

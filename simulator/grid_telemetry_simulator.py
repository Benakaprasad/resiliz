"""
ResiliZ Microgrid Telemetry Simulator
Generates realistic electrical telemetry (voltage, current, frequency, load, solar, battery)
with dynamic physical modeling and controllable anomaly injection.
"""

import time
import math
import random
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Generator, Callable

logger = logging.getLogger("resiliz.simulator")

class MicrogridTelemetrySimulator:
    def __init__(
        self,
        grid_id: str = "MG-ALPHA-01",
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
        self.battery_soc_pct = 76.5  # Initial 76.5%
        self.base_load_kw = base_load_kw
        
        # Operational State
        self.grid_connected = True
        self.tick_counter = 0
        self.start_epoch = time.time()
        
        # Controlled Anomaly State
        self.active_anomaly: Optional[str] = None
        self.anomaly_remaining_ticks: int = 0
        self.anomaly_intensity: float = 1.0
        self.anomaly_metadata: Dict[str, Any] = {}

    def inject_anomaly(self, anomaly_type: str, duration_ticks: int = 15, intensity: float = 1.0, metadata: Optional[Dict[str, Any]] = None):
        """
        Inject a controlled anomaly into the telemetry stream.
        Types:
            - 'voltage_sag': Sudden voltage drop (e.g., feeder fault, motor startup)
            - 'voltage_swell': Sudden voltage surge (e.g., sudden load disconnection)
            - 'frequency_instability': Grid disconnect or loss of generation droop
            - 'reverse_power_flow': Excessive PV injection into unbuffered feeder
            - 'transient_spike': 1-tick benign electrical noise (test false-alarm filter)
            - 'cyber_sensor_tampering': Drift/spoofed readings or sensor freeze
        """
        self.active_anomaly = anomaly_type
        self.anomaly_remaining_ticks = duration_ticks
        self.anomaly_intensity = intensity
        self.anomaly_metadata = metadata or {}
        logger.info(f"Injected anomaly [{anomaly_type}] for {duration_ticks} ticks (intensity={intensity})")

    def clear_anomaly(self):
        """Manually clear any ongoing anomaly."""
        prev = self.active_anomaly
        self.active_anomaly = None
        self.anomaly_remaining_ticks = 0
        self.anomaly_intensity = 1.0
        self.anomaly_metadata = {}
        if prev:
            logger.info(f"Anomaly [{prev}] cleared.")

    def step(self) -> Dict[str, Any]:
        """
        Generate the next single tick of microgrid electrical telemetry.
        """
        self.tick_counter += 1
        now = datetime.now(timezone.utc)
        sim_time = self.tick_counter * 0.5  # simulated time progress

        # Diurnal Solar Profile (sinusoidal peak at mid-day)
        # Using a 24-minute full cycle for rapid visual testing, or daily clock
        time_cycle = (self.tick_counter % 240) / 240.0 * 24.0  # 0 to 24 hours
        if 6.0 <= time_cycle <= 18.0:
            solar_peak_ratio = math.sin((time_cycle - 6.0) / 12.0 * math.pi)
            # Add small random cloud variations (+/- 8%)
            cloud_factor = max(0.0, min(1.0, 0.95 + random.uniform(-0.08, 0.05)))
            solar_pv_kw = round(self.solar_capacity_kw * solar_peak_ratio * cloud_factor, 2)
        else:
            solar_pv_kw = 0.0

        # Dynamic Load Demand
        load_diurnal = math.sin((time_cycle - 8.0) / 24.0 * 2 * math.pi) * 8.0
        load_noise = random.gauss(0, 1.2)
        load_kw = max(8.0, round(self.base_load_kw + load_diurnal + load_noise, 2))

        # Battery Discharging / Charging Dynamics
        net_renewable = solar_pv_kw - load_kw
        if net_renewable > 0:
            # Solar surplus: charge battery up to 98%
            if self.battery_soc_pct < 98.0:
                battery_power_kw = round(min(net_renewable * 0.85, 25.0), 2)  # positive = charging
                self.battery_soc_pct += (battery_power_kw / self.battery_capacity_kwh) * (0.5 / 3600) * 100
            else:
                battery_power_kw = 0.0
        else:
            # Deficit: discharge battery down to 15%
            if self.battery_soc_pct > 15.0:
                battery_power_kw = round(max(net_renewable, -25.0), 2)  # negative = discharging
                self.battery_soc_pct += (battery_power_kw / self.battery_capacity_kwh) * (0.5 / 3600) * 100
            else:
                battery_power_kw = 0.0
        self.battery_soc_pct = round(max(10.0, min(100.0, self.battery_soc_pct)), 2)

        # Baseline Electrical Parameters
        voltage_v = self.nominal_voltage + random.gauss(0, 0.6)  # ~230V +/- 0.6V normal noise
        frequency_hz = self.nominal_frequency + random.gauss(0, 0.015)  # ~50Hz +/- 0.015Hz
        power_factor = round(0.95 + random.uniform(-0.02, 0.02), 3)

        # Calculate reactive power and current
        active_power_kw = load_kw
        reactive_power_kvar = round(active_power_kw * math.tan(math.acos(power_factor)), 2)
        current_a = round((active_power_kw * 1000.0) / (voltage_v * power_factor), 2)

        # Apply Injected Anomaly Modifiers
        is_ground_truth_anomaly = False
        anomaly_label = "NORMAL"

        if self.anomaly_remaining_ticks > 0 and self.active_anomaly:
            is_ground_truth_anomaly = True
            anomaly_label = self.active_anomaly
            self.anomaly_remaining_ticks -= 1

            if self.active_anomaly == "voltage_sag":
                # Drops to 160V - 180V
                drop_amount = 55.0 * self.anomaly_intensity
                voltage_v = max(140.0, voltage_v - drop_amount)
                current_a = round(current_a * 1.35, 2)  # Inrush or fault current surge

            elif self.active_anomaly == "voltage_swell":
                # Surges to 265V - 280V
                surge_amount = 45.0 * self.anomaly_intensity
                voltage_v = min(300.0, voltage_v + surge_amount)

            elif self.active_anomaly == "frequency_instability":
                # Frequency wanders significantly out of normal 49.5 - 50.5 range
                freq_shift = 1.1 * self.anomaly_intensity * (-1 if (self.tick_counter % 2 == 0) else 1)
                frequency_hz = round(self.nominal_frequency + freq_shift + random.gauss(0, 0.1), 3)

            elif self.active_anomaly == "reverse_power_flow":
                # Severe reverse power backfeeding without balance
                solar_pv_kw = round(solar_pv_kw * 1.5, 2)
                reactive_power_kvar = round(-12.0 * self.anomaly_intensity, 2)
                power_factor = 0.68  # Poor reactive power factor

            elif self.active_anomaly == "transient_spike":
                # 1-sample transient electrical spike
                voltage_v += 38.0 * self.anomaly_intensity
                current_a += 25.0 * self.anomaly_intensity
                # Reset immediately after single tick
                self.anomaly_remaining_ticks = 0

            elif self.active_anomaly == "cyber_sensor_tampering":
                # Freezes or outputs erratic out-of-physical bounds data
                if self.tick_counter % 2 == 0:
                    voltage_v = 0.0  # spoofed outage
                    current_a = 99.9
                else:
                    voltage_v = 310.5
                    frequency_hz = 35.0

            if self.anomaly_remaining_ticks == 0:
                self.active_anomaly = None

        voltage_v = round(voltage_v, 2)
        frequency_hz = round(frequency_hz, 3)
        current_a = round(current_a, 2)

        record = {
            "timestamp": now.isoformat(),
            "tick": self.tick_counter,
            "grid_id": self.grid_id,
            "voltage_v": voltage_v,
            "current_a": current_a,
            "frequency_hz": frequency_hz,
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
        return record

    def stream(self, interval_seconds: float = 1.0) -> Generator[Dict[str, Any], None, None]:
        """Continuous stream generator for telemetry readings."""
        while True:
            yield self.step()
            time.sleep(interval_seconds)


class KafkaTelemetryProducer:
    """
    Kafka Producer for streaming microgrid telemetry to Apache Kafka topic.
    Includes automatic graceful degradation: if Kafka broker is unavailable,
    falls back cleanly without crashing the pipeline.
    """
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
                request_timeout_ms=3000,
            )
            self.is_connected = True
            logger.info(f"Connected to Kafka broker at {self.bootstrap_servers}, topic: {self.topic}")
        except Exception as e:
            self.is_connected = False
            logger.warning(f"Kafka broker at {self.bootstrap_servers} unavailable ({e}). Running in direct fallback mode.")

    def send(self, telemetry: Dict[str, Any]):
        if self.is_connected and self.producer:
            try:
                self.producer.send(self.topic, key=telemetry.get("grid_id", "default"), value=telemetry)
            except Exception as e:
                logger.error(f"Failed to publish to Kafka: {e}")
                self.is_connected = False
        return telemetry


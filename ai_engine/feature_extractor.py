"""
ResiliZ Telemetry Feature Extractor
Processes raw electrical readings into rolling statistical and physical features.
"""

from collections import deque
from typing import Dict, Any, List
import numpy as np

FEATURE_NAMES = [
    "voltage_v",
    "voltage_rolling_mean",
    "voltage_rolling_std",
    "voltage_p2p",
    "frequency_hz",
    "frequency_rolling_mean",
    "frequency_rocof",  # |df/dt|
    "current_a",
    "current_rolling_mean",
    "active_power_kw",
    "reactive_power_kvar",
    "power_factor",
    "net_renewable_balance_kw",
    "battery_soc_pct",
]

class TelemetryFeatureExtractor:
    def __init__(self, window_size: int = 10):
        self.window_size = window_size
        self.voltage_history = deque(maxlen=window_size)
        self.frequency_history = deque(maxlen=window_size)
        self.current_history = deque(maxlen=window_size)
        self.last_frequency = None
        self.last_timestamp = None

    def update_and_extract(self, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Ingests a telemetry record, updates rolling windows, and outputs
        the extracted feature dictionary and numeric array.
        """
        v = float(telemetry.get("voltage_v", 230.0))
        f = float(telemetry.get("frequency_hz", 50.0))
        c = float(telemetry.get("current_a", 15.0))
        p = float(telemetry.get("active_power_kw", 25.0))
        q = float(telemetry.get("reactive_power_kvar", 5.0))
        pf = float(telemetry.get("power_factor", 0.95))
        solar = float(telemetry.get("solar_pv_kw", 0.0))
        batt_p = float(telemetry.get("battery_power_kw", 0.0))
        soc = float(telemetry.get("battery_soc_pct", 75.0))

        # Append to histories
        self.voltage_history.append(v)
        self.frequency_history.append(f)
        self.current_history.append(c)

        # Voltage rolling metrics
        v_mean = float(np.mean(self.voltage_history))
        v_std = float(np.std(self.voltage_history)) if len(self.voltage_history) > 1 else 0.0
        v_p2p = float(max(self.voltage_history) - min(self.voltage_history))

        # Frequency rolling metrics & ROCOF (Rate of Change of Frequency)
        f_mean = float(np.mean(self.frequency_history))
        if self.last_frequency is not None:
            # Absolute frequency derivative per tick
            rocof = abs(f - self.last_frequency)
        else:
            rocof = 0.0
        self.last_frequency = f

        # Current rolling metrics
        c_mean = float(np.mean(self.current_history))

        # Net balance: Solar + Battery - Load
        net_balance = round(solar + batt_p - p, 2)

        features = {
            "voltage_v": v,
            "voltage_rolling_mean": round(v_mean, 2),
            "voltage_rolling_std": round(v_std, 3),
            "voltage_p2p": round(v_p2p, 2),
            "frequency_hz": f,
            "frequency_rolling_mean": round(f_mean, 3),
            "frequency_rocof": round(rocof, 4),
            "current_a": c,
            "current_rolling_mean": round(c_mean, 2),
            "active_power_kw": p,
            "reactive_power_kvar": q,
            "power_factor": pf,
            "net_renewable_balance_kw": net_balance,
            "battery_soc_pct": soc,
        }

        feature_vector = [features[name] for name in FEATURE_NAMES]
        return {
            "features": features,
            "feature_vector": feature_vector,
            "feature_names": FEATURE_NAMES,
        }


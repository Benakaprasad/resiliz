"""
ResiliZ Kafka Telemetry Consumer
Consumes timestamped telemetry events from the Kafka topic and feeds them to the AI detection engine.
"""

import json
import logging
from typing import Callable, Optional

logger = logging.getLogger("resiliz.kafka_consumer")

class TelemetryKafkaConsumer:
    def __init__(
        self,
        bootstrap_servers: str = "localhost:9092",
        topic: str = "microgrid-telemetry",
        group_id: str = "resiliz-ai-detectors",
    ):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.consumer = None
        self.is_connected = False

    def start(self, on_message: Callable[[dict], None]):
        """Connect and begin consuming messages, invoking callback for each."""
        try:
            from kafka import KafkaConsumer
            self.consumer = KafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode("utf-8")),
                auto_offset_reset="latest",
                enable_auto_commit=True,
                request_timeout_ms=5000,
            )
            self.is_connected = True
            logger.info(f"Consuming from Kafka topic '{self.topic}' at {self.bootstrap_servers}")

            for message in self.consumer:
                telemetry = message.value
                on_message(telemetry)
        except Exception as e:
            self.is_connected = False
            logger.warning(f"Kafka consumer connection to {self.bootstrap_servers} failed: {e}")

    def close(self):
        if self.consumer:
            self.consumer.close()
            self.is_connected = False


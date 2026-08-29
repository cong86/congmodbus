"""Shared runtime state for congmodbus entities."""

import time
from datetime import datetime


RUNTIME_STORE_KEY = "congmodbus_poll_runtime"


class PollingRuntime:
    """Shared polling state for one modbus hub."""

    def __init__(self, hub_name):
        self.hub_name = hub_name
        self.manual_polling_enabled = True
        self.poll_paused = False
        self.error_count = 0

        self.retry_seconds = 30
        self.max_retry_seconds = 300

        self.next_poll_retry_at = 0.0
        self.next_poll_retry_wall = None

        self.last_error_at = None
        self.last_recovered_at = None

        self.sensor_loaded = False
        self.switch_loaded = False
        self.setup_count = 0
        self.reload_reconnect_pending = False
        self.generation = 0
        self.last_setup_at = 0.0
        self.guarded_generation = 0
        self.warmup_until = 0.0
        self.suppress_warning_until = 0.0

        # Climate entities are the single source of Modbus fan-speed reads.
        # ActualFanSpeedSensor entities subscribe to these cached samples so
        # they do not issue duplicate requests or bypass polling backoff.
        self._fan_speed_samples = {}
        self._fan_speed_listeners = {}

    def retry_in_seconds(self):
        if not self.poll_paused:
            return 0
        return max(0, int(self.next_poll_retry_at - time.monotonic()))

    @property
    def state(self):
        if not self.manual_polling_enabled:
            return "手动关闭"
        return "停止" if self.poll_paused else "运行"

    @staticmethod
    def _fan_speed_key(slave, register):
        return (int(slave), int(register))

    def get_fan_speed_sample(self, slave, register):
        """Return the latest cached fan-speed sample, if any."""
        return self._fan_speed_samples.get(self._fan_speed_key(slave, register))

    def add_fan_speed_listener(self, slave, register, listener):
        """Subscribe to cached fan-speed changes and return an unsubscribe callback."""
        key = self._fan_speed_key(slave, register)
        listeners = self._fan_speed_listeners.setdefault(key, set())
        listeners.add(listener)

        def remove_listener():
            current = self._fan_speed_listeners.get(key)
            if current is None:
                return
            current.discard(listener)
            if not current:
                self._fan_speed_listeners.pop(key, None)

        return remove_listener

    def publish_fan_speed(self, slave, register, raw_value):
        """Publish a successful fan-speed read to subscribed sensor entities."""
        key = self._fan_speed_key(slave, register)
        previous = self._fan_speed_samples.get(key)
        sample = {
            "raw_value": raw_value,
            "available": True,
            "updated_at": datetime.now().astimezone(),
        }
        self._fan_speed_samples[key] = sample

        if (
            previous is None
            or not previous.get("available", False)
            or previous.get("raw_value") != raw_value
        ):
            self._notify_fan_speed_listeners(key, sample)

    def mark_fan_speeds_unavailable(self):
        """Mark cached fan speeds unavailable when the shared hub poll fails."""
        for key, previous in list(self._fan_speed_samples.items()):
            if not previous.get("available", False):
                continue
            sample = dict(previous)
            sample["available"] = False
            self._fan_speed_samples[key] = sample
            self._notify_fan_speed_listeners(key, sample)

    def _notify_fan_speed_listeners(self, key, sample):
        for listener in tuple(self._fan_speed_listeners.get(key, ())):
            listener(sample)


def get_polling_runtime(hass, hub_name):
    """Return shared runtime for a hub."""
    store = hass.data.setdefault(RUNTIME_STORE_KEY, {})
    runtime = store.get(hub_name)
    if runtime is None:
        runtime = PollingRuntime(hub_name)
        store[hub_name] = runtime
    return runtime

"""Shared runtime state for zhimodbus entities."""

import time


RUNTIME_STORE_KEY = "zhimodbus_poll_runtime"


class PollingRuntime:
    """Shared polling state for one modbus hub."""

    def __init__(self, hub_name):
        self.hub_name = hub_name
        self.poll_paused = False
        self.error_count = 0

        self.retry_seconds = 30
        self.max_retry_seconds = 300

        self.next_poll_retry_at = 0.0
        self.next_poll_retry_wall = None

        self.last_error_at = None
        self.last_recovered_at = None

        self.sensor_loaded = False
        self.setup_count = 0
        self.reload_reconnect_pending = False
        self.generation = 0
        self.last_setup_at = 0.0
        self.guarded_generation = 0
        self.warmup_until = 0.0
        self.suppress_warning_until = 0.0

    def retry_in_seconds(self):
        if not self.poll_paused:
            return 0
        return max(0, int(self.next_poll_retry_at - time.monotonic()))

    @property
    def state(self):
        return "停止" if self.poll_paused else "运行"


def get_polling_runtime(hass, hub_name):
    """Return shared runtime for a hub."""
    store = hass.data.setdefault(RUNTIME_STORE_KEY, {})
    runtime = store.get(hub_name)
    if runtime is None:
        runtime = PollingRuntime(hub_name)
        store[hub_name] = runtime
    return runtime

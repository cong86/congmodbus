"""Status sensor for congmodbus polling."""

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.modbus.const import DEFAULT_HUB
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from .runtime import get_polling_runtime


SCAN_INTERVAL = timedelta(seconds=10)
DEFAULT_NAME = "ModBus Polling"
CONF_HUB = "hub"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, conf, add_devices, discovery_info=None):
    """Set up congmodbus polling status sensor."""
    if discovery_info:
        hub_name = discovery_info.get(CONF_HUB, DEFAULT_HUB)
        name = discovery_info.get(CONF_NAME, DEFAULT_NAME)
    else:
        hub_name = conf.get(CONF_HUB)
        name = conf.get(CONF_NAME)

    runtime = get_polling_runtime(hass, hub_name)
    add_devices([CongModbusPollingSensor(runtime, name)], True)


class CongModbusPollingSensor(SensorEntity):
    """Expose polling state for dashboard cards."""

    def __init__(self, runtime, name):
        self._runtime = runtime
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        from homeassistant.util import slugify

        return "congmodbus.polling." + slugify(self._runtime.hub_name)

    @property
    def native_value(self):
        return self._runtime.state

    @property
    def icon(self):
        return "mdi:close-circle" if self._runtime.poll_paused else "mdi:check-circle"

    @property
    def extra_state_attributes(self):
        attrs = {
            "hub": self._runtime.hub_name,
            "error_count": self._runtime.error_count,
            "retry_seconds": self._runtime.retry_seconds,
            "max_retry_seconds": self._runtime.max_retry_seconds,
        }

        if self._runtime.poll_paused:
            attrs["next_retry_in"] = self._runtime.retry_in_seconds()
            if self._runtime.next_poll_retry_wall is not None:
                attrs["next_retry_at"] = self._runtime.next_poll_retry_wall.isoformat()

        if self._runtime.last_error_at is not None:
            attrs["last_error_at"] = self._runtime.last_error_at.isoformat()

        if self._runtime.last_recovered_at is not None:
            attrs["last_recovered_at"] = self._runtime.last_recovered_at.isoformat()

        return attrs

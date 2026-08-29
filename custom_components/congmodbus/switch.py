"""Polling control switch for congmodbus."""

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.modbus.const import DEFAULT_HUB
from homeassistant.components.switch import PLATFORM_SCHEMA, SwitchEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv

from .runtime import get_polling_runtime


SCAN_INTERVAL = timedelta(seconds=10)
DEFAULT_NAME = "ModBus Polling Switch"
CONF_HUB = "hub"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    }
)


def setup_platform(hass, conf, add_devices, discovery_info=None):
    """Set up congmodbus polling control switch."""
    if discovery_info:
        hub_name = discovery_info.get(CONF_HUB, DEFAULT_HUB)
        name = discovery_info.get(CONF_NAME, DEFAULT_NAME)
    else:
        hub_name = conf.get(CONF_HUB)
        name = conf.get(CONF_NAME)

    runtime = get_polling_runtime(hass, hub_name)
    add_devices([CongModbusPollingSwitch(runtime, name)], True)


class CongModbusPollingSwitch(SwitchEntity):
    """Manual on/off switch for congmodbus polling."""

    def __init__(self, runtime, name):
        self._runtime = runtime
        self._name = name

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        from homeassistant.util import slugify

        return "congmodbus.polling_switch." + slugify(self._runtime.hub_name)

    @property
    def is_on(self):
        return self._runtime.manual_polling_enabled

    @property
    def icon(self):
        return "mdi:play-circle" if self.is_on else "mdi:pause-circle"

    @property
    def extra_state_attributes(self):
        return {"hub": self._runtime.hub_name}

    async def async_turn_on(self, **kwargs):
        # 重新打开时允许下一轮立即探测，避免等待退避窗口。
        self._runtime.manual_polling_enabled = True
        self._runtime.next_poll_retry_at = 0.0
        self._runtime.next_poll_retry_wall = None
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        self._runtime.manual_polling_enabled = False
        self._runtime.next_poll_retry_wall = None
        self.async_write_ha_state()

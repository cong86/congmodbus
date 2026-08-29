"""Sensors for congmodbus: polling status and per-unit actual fan speed."""

from datetime import timedelta

import voluptuous as vol

from homeassistant.components.modbus.const import DEFAULT_HUB
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, CONF_SLAVE
import homeassistant.helpers.config_validation as cv

from .runtime import get_polling_runtime


SCAN_INTERVAL = timedelta(seconds=10)
DEFAULT_NAME = "ModBus Polling"
CONF_HUB = "hub"
CONF_REGISTER = "register"

# 厂商 Word 105 风速读取映射（01-0B）
ACTUAL_FAN_SPEED_MAP = {
    0x01: "风机停",
    0x02: "超低速",
    0x03: "低档",
    0x04: "中低档",
    0x05: "中档",
    0x06: "中高档",
    0x07: "高档",
    0x08: "超高速",
    0x09: "静音R1",
    0x0A: "静音R2",
    0x0B: "静音R3",
}
FAN_SPEED_UNKNOWN = "无效"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_SLAVE): cv.positive_int,
        vol.Optional(CONF_REGISTER): cv.positive_int,
    }
)


def setup_platform(hass, conf, add_devices, discovery_info=None):
    """Set up congmodbus sensors."""
    if discovery_info:
        hub_name = discovery_info.get(CONF_HUB, DEFAULT_HUB)
        name = discovery_info.get(CONF_NAME, DEFAULT_NAME)
    else:
        hub_name = conf.get(CONF_HUB)
        name = conf.get(CONF_NAME)

    # 带 register/slave 的配置项为实际风速传感器；否则为轮询状态传感器
    if conf.get(CONF_REGISTER) is not None and conf.get(CONF_SLAVE) is not None:
        add_devices(
            [ActualFanSpeedSensor(hass, hub_name, name, conf[CONF_SLAVE], conf[CONF_REGISTER])],
            True,
        )
        return

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
        if not self._runtime.manual_polling_enabled:
            return "mdi:pause-circle"
        return "mdi:close-circle" if self._runtime.poll_paused else "mdi:check-circle"

    @property
    def extra_state_attributes(self):
        attrs = {
            "hub": self._runtime.hub_name,
            "manual_polling_enabled": self._runtime.manual_polling_enabled,
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


class ActualFanSpeedSensor(SensorEntity):
    """展示 Climate 轮询得到的 Word 105 实际风速（01-0B 厂商映射）。

    与 climate 的 fan_mode 设定值相互独立，但不重复访问 Modbus：
    Climate 是唯一读取者，本传感器订阅共享运行时缓存。
    """

    _attr_should_poll = False

    def __init__(self, hass, hub_name, name, slave, register):
        self.hass = hass
        self._hub_name = hub_name
        self._name = name
        self._slave = slave
        self._register = register
        self._state = None
        self._raw_value = None
        self._last_update = None
        self._remove_listener = None
        self._runtime = get_polling_runtime(hass, hub_name)
        self._attr_available = False

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        from homeassistant.util import slugify

        return f"congmodbus.actual_fan.{slugify(self._name)}"

    @property
    def native_value(self):
        return self._state

    @property
    def icon(self):
        return "mdi:fan"

    @property
    def extra_state_attributes(self):
        return {
            "hub": self._hub_name,
            "slave": self._slave,
            "register": self._register,
            "raw_value": self._raw_value,
            "source": "climate_shared_poll",
            "last_update": self._last_update.isoformat() if self._last_update else None,
        }

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        sample = self._runtime.get_fan_speed_sample(self._slave, self._register)
        if sample is not None:
            self._apply_sample(sample)
        self._remove_listener = self._runtime.add_fan_speed_listener(
            self._slave, self._register, self._handle_sample
        )

    async def async_will_remove_from_hass(self):
        if self._remove_listener is not None:
            self._remove_listener()
            self._remove_listener = None
        await super().async_will_remove_from_hass()

    def _handle_sample(self, sample):
        self._apply_sample(sample)
        self.async_write_ha_state()

    def _apply_sample(self, sample):
        self._attr_available = bool(sample.get("available"))
        self._raw_value = sample.get("raw_value")
        self._last_update = sample.get("updated_at")
        self._state = ACTUAL_FAN_SPEED_MAP.get(self._raw_value, FAN_SPEED_UNKNOWN)

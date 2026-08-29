"""Sensors for congmodbus: polling status and per-unit actual fan speed."""

import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

from homeassistant.components.modbus.const import (
    DEFAULT_HUB,
    MODBUS_DOMAIN,
    CALL_TYPE_REGISTER_HOLDING,
)
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_NAME, CONF_SLAVE
import homeassistant.helpers.config_validation as cv

from .runtime import get_polling_runtime


_LOGGER = logging.getLogger(__name__)

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
    """读取格力 Word 105 实际风速寄存器（01-0B 厂商映射）。

    与 climate 的 fan_mode 设定值(Word 104)相互独立：
    climate 负责写入风速设定，本传感器只读实际运行风速。
    所有读取复用组件的 I/O 锁，避免与 climate 轮询并发。
    """

    def __init__(self, hass, hub_name, name, slave, register):
        self.hass = hass
        self._hub_name = hub_name
        self._name = name
        self._slave = slave
        self._register = register
        self._state = None
        self._raw_value = None

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
        }

    async def async_update(self):
        """每 SCAN_INTERVAL 读取一次实际风速寄存器。"""
        hub = self.hass.data.get(MODBUS_DOMAIN, {}).get(self._hub_name)
        if hub is None:
            _LOGGER.warning("Actual fan speed %s: modbus hub %s not found", self._name, self._hub_name)
            self._state = "不可用"
            return

        # 复用 climate 组件的 I/O 锁，避免与现有 20 个轮询请求并发
        lock = self.hass.data.setdefault("congmodbus_io_locks", {}).setdefault(
            self._hub_name, asyncio.Lock()
        )
        try:
            async with lock:
                result = await hub.async_pb_call(
                    self._slave, self._register, 1, CALL_TYPE_REGISTER_HOLDING
                )
            value = result.registers[0]
            self._raw_value = value
            self._state = ACTUAL_FAN_SPEED_MAP.get(value, FAN_SPEED_UNKNOWN)
        except Exception as err:
            _LOGGER.warning(
                "Actual fan speed %s (reg %d) read failed: %s",
                self._name, self._register, err,
            )
            self._state = "不可用"

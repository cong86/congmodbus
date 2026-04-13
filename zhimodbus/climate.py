"""ZhiModbus 温控平台。

用于在 Home Assistant 中接入基于 Modbus 的温控设备，
支持温度读写、模式切换，以及在通信异常时的轮询熔断与恢复。
"""

import logging
import asyncio
import time
import struct
from datetime import timedelta, datetime

import voluptuous as vol

from homeassistant.components.climate import ClimateEntity, PLATFORM_SCHEMA
from homeassistant.components.climate.const import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import CONF_NAME, CONF_SLAVE, CONF_OFFSET, CONF_STRUCTURE, ATTR_TEMPERATURE
from homeassistant.components.modbus.const import (
    DEFAULT_HUB, MODBUS_DOMAIN,
    CALL_TYPE_COIL, CALL_TYPE_REGISTER_HOLDING, CALL_TYPE_REGISTER_INPUT,
)
import homeassistant.helpers.config_validation as cv

from .runtime import get_polling_runtime


_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=10)
PARALLEL_UPDATES = 1
PENDING_SECONDS = 20
# 通讯失败后的重试基准秒数与最大退避上限。
DEFAULT_POLL_RETRY_SECONDS = 20
DEFAULT_MAX_POLL_RETRY_SECONDS = 120

CONF_AUX_HEAT_OFF_VALUE = "aux_heat_off_value"
CONF_AUX_HEAT_ON_VALUE = "aux_heat_on_value"
CONF_COUNT = "count"
CONF_DATA_TYPE = "data_type"
CONF_FAN_MODES = "fan_modes"
CONF_HVAC_MODES = "hvac_modes"
CONF_HVAC_OFF_VALUE = "hvac_off_value"
CONF_HVAC_ON_VALUE = "hvac_on_value"
CONF_MAX_POLL_RETRY_SECONDS = "max_poll_retry_seconds"
CONF_POLL_RETRY_SECONDS = "poll_retry_seconds"
CONF_PRESET_MODES = "preset_mode"
CONF_REGISTER = "register"
CONF_REGISTER_TYPE = "register_type"
CONF_REGISTERS = "registers"
CONF_REVERSE_ORDER = "reverse_order"
CONF_SCALE = "scale"
CONF_SWING_MODES = "swing_modes"

REG_AUX_HEAT = "aux_heat"
REG_FAN_MODE = "fan_mode"
REG_HUMIDITY = "humidity"
REG_HVAC_MODE = "hvac_mode"
REG_HVAC_OFF = "hvac_off"
REG_PRESET_MODE = "preset_mode"
REG_SWING_MODE = "swing_mode"
REG_TARGET_HUMIDITY = "target_humidity"
REG_TARGET_TEMPERATURE = "target_temperature"
REG_TEMPERATURE = "temperature"

REGISTER_TYPE_HOLDING = "holding"
REGISTER_TYPE_INPUT = "input"
REGISTER_TYPE_COIL = "coil"

DATA_TYPE_INT = "int"
DATA_TYPE_UINT = "uint"
DATA_TYPE_FLOAT = "float"
DATA_TYPE_CUSTOM = "custom"

SUPPORTED_FEATURES = {
    REG_FAN_MODE: ClimateEntityFeature.FAN_MODE,
    REG_HUMIDITY: 0,
    REG_HVAC_MODE: ClimateEntityFeature.TURN_ON,
    REG_HVAC_OFF: ClimateEntityFeature.TURN_OFF,
    REG_PRESET_MODE: ClimateEntityFeature.PRESET_MODE,
    REG_SWING_MODE: ClimateEntityFeature.SWING_MODE,
    REG_TARGET_HUMIDITY: ClimateEntityFeature.TARGET_HUMIDITY,
    REG_TARGET_TEMPERATURE: ClimateEntityFeature.TARGET_TEMPERATURE,
    REG_TEMPERATURE: 0,
}

HVAC_ACTIONS = {
    HVACMode.OFF: HVACAction.OFF,
    HVACMode.HEAT: HVACAction.HEATING,
    HVACMode.COOL: HVACAction.COOLING,
    HVACMode.HEAT_COOL: HVACAction.IDLE,
    HVACMode.AUTO: HVACAction.IDLE,
    HVACMode.DRY: HVACAction.DRYING,
    HVACMode.FAN_ONLY: HVACAction.FAN,
}

DEFAULT_NAME = "ModBus"
CONF_HUB = "hub"
DOMAIN = "zhimodbus"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_HUB, default=DEFAULT_HUB): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): vol.Any(cv.string, list),

    vol.Optional(CONF_FAN_MODES, default={}): dict,
    vol.Optional(CONF_HVAC_MODES, default={}): dict,
    vol.Optional(CONF_PRESET_MODES, default={}): dict,
    vol.Optional(CONF_SWING_MODES, default={}): dict,
    vol.Optional(CONF_AUX_HEAT_OFF_VALUE, default=0): int,
    vol.Optional(CONF_AUX_HEAT_ON_VALUE, default=1): int,
    vol.Optional(CONF_HVAC_OFF_VALUE, default=0): int,
    vol.Optional(CONF_HVAC_ON_VALUE, default=1): int,
    vol.Optional(CONF_POLL_RETRY_SECONDS, default=DEFAULT_POLL_RETRY_SECONDS): vol.All(
        vol.Coerce(int), vol.Range(min=5)
    ),
    vol.Optional(CONF_MAX_POLL_RETRY_SECONDS, default=DEFAULT_MAX_POLL_RETRY_SECONDS): vol.All(
        vol.Coerce(int), vol.Range(min=5)
    ),

    vol.Optional(REG_AUX_HEAT): dict,
    vol.Optional(REG_FAN_MODE): dict,
    vol.Optional(REG_HUMIDITY): dict,
    vol.Optional(REG_HVAC_MODE): dict,
    vol.Optional(REG_HVAC_OFF): dict,
    vol.Optional(REG_PRESET_MODE): dict,
    vol.Optional(REG_SWING_MODE): dict,
    vol.Optional(REG_TARGET_HUMIDITY): dict,
    vol.Optional(REG_TARGET_TEMPERATURE): dict,
    vol.Optional(REG_TEMPERATURE): dict,
})


def setup_platform(hass, conf, add_devices, discovery_info=None):
    """初始化 Modbus 温控平台并创建实体。"""
    name = conf.get(CONF_NAME)
    bus = ClimateModbus(hass, conf)
    if not bus.regs:
        _LOGGER.error("Invalid config %s: no modbus items", name)
        return

    entities = []
    # 多设备场景：根据寄存器数组长度按索引生成实体。
    for index in range(100):
        if not bus.has_valid_register(index):
            break
        entities.append(
            ZhiModbusClimate(
                bus,
                name[index] if isinstance(name, list) else (name + str(index + 1)),
                index,
            )
        )

    if not entities:
        for prop in bus.regs:
            if CONF_REGISTER not in bus.regs[prop]:
                _LOGGER.error("Invalid config %s/%s: no register", name, prop)
                return
        entities.append(ZhiModbusClimate(bus, name[0] if isinstance(name, list) else name))

    bus.count = len(entities)
    status_name = bus.hub_name + " Polling"
    bus.ensure_status_sensor(status_name)
    add_devices(entities, False)


class ClimateModbus:
    """封装 Modbus 读写与轮询状态控制。"""

    def __init__(self, hass, conf):
        self.error = 0
        self.hass = hass
        self.hub_name = conf.get(CONF_HUB)
        self.hub = self.hass.data[MODBUS_DOMAIN][self.hub_name]
        # 同一 hub 下所有实体共享 I/O 锁，避免并发读写打架。
        hub_locks = self.hass.data.setdefault("zhimodbus_io_locks", {})
        self._io_lock = hub_locks.setdefault(self.hub_name, asyncio.Lock())
        self._reconnect_pending = False
        self._next_reconnect_at = 0.0
        self._poll_probe_in_progress = False
        self._poll_retry_seconds = conf.get(CONF_POLL_RETRY_SECONDS, DEFAULT_POLL_RETRY_SECONDS)
        self._max_poll_retry_seconds = conf.get(CONF_MAX_POLL_RETRY_SECONDS, DEFAULT_MAX_POLL_RETRY_SECONDS)
        if self._max_poll_retry_seconds < self._poll_retry_seconds:
            self._max_poll_retry_seconds = self._poll_retry_seconds
        self._poll_runtime = get_polling_runtime(hass, self.hub_name)
        self._poll_runtime.retry_seconds = self._poll_retry_seconds
        self._poll_runtime.max_retry_seconds = self._max_poll_retry_seconds
        self.unit = hass.config.units.temperature_unit
        self.fan_modes = conf.get(CONF_FAN_MODES)
        self.hvac_modes = conf.get(CONF_HVAC_MODES)
        self.preset_modes = conf.get(CONF_PRESET_MODES)
        self.swing_modes = conf.get(CONF_SWING_MODES)
        self.hvac_off_value = conf.get(CONF_HVAC_OFF_VALUE)
        self.hvac_on_value = conf.get(CONF_HVAC_ON_VALUE)
        self.aux_heat_on_value = conf.get(CONF_AUX_HEAT_ON_VALUE)
        self.aux_heat_off_value = conf.get(CONF_AUX_HEAT_OFF_VALUE)

        data_types = {DATA_TYPE_INT: {1: "h", 2: "i", 4: "q"}}
        data_types[DATA_TYPE_UINT] = {1: "H", 2: "I", 4: "Q"}
        data_types[DATA_TYPE_FLOAT] = {1: "e", 2: "f", 4: "d"}

        # 解析并缓存所有功能对应的寄存器定义。
        self.regs = {}
        for prop in SUPPORTED_FEATURES:
            reg = conf.get(prop)
            if not reg:
                continue

            count = reg.get(CONF_COUNT, 1)
            data_type = reg.get(CONF_DATA_TYPE)
            if data_type != DATA_TYPE_CUSTOM:
                try:
                    reg[CONF_STRUCTURE] = ">{}".format(
                        data_types[DATA_TYPE_INT if data_type is None else data_type][count]
                    )
                except KeyError:
                    _LOGGER.error("Unable to detect data type for %s", prop)
                    continue

            try:
                size = struct.calcsize(reg[CONF_STRUCTURE])
            except struct.error as err:
                _LOGGER.error("Error in sensor %s structure: %s", prop, err)
                continue

            if count * 2 != size:
                _LOGGER.error(
                    "Structure size (%d bytes) mismatch registers count (%d words)",
                    size, count
                )
                continue

            self.regs[prop] = reg


    def has_valid_register(self, index):
        """检查每个功能项在给定索引上是否都有可用寄存器。"""
        for prop in self.regs:
            registers = self.regs[prop].get(CONF_REGISTERS)
            if not registers or index >= len(registers):
                return False
        return True

    def reset(self):
        _LOGGER.warning("Skip raw reset on %s", self.hub._client)

    async def reconnect(self, now=None):
        """调度执行 hub 重连，并设置下一次可重连时间。"""
        _LOGGER.warning("Reconnect %s", self.hub._client)
        try:
            async with self._io_lock:
                await self.hub.async_restart()
        except Exception as err:
            _LOGGER.warning("Reconnect failed on %s: %s", self.hub_name, err)
        finally:
            self._reconnect_pending = False
            self._next_reconnect_at = time.monotonic() + 15

    def ensure_status_sensor(self, name):
        """确保轮询状态传感器仅加载一次。"""
        if self._poll_runtime.sensor_loaded:
            return

        self._poll_runtime.sensor_loaded = True
        from homeassistant.helpers import discovery

        discovery.load_platform(
            self.hass,
            "sensor",
            DOMAIN,
            {CONF_HUB: self.hub_name, CONF_NAME: name},
            {},
        )

    def should_poll(self):
        if not self._poll_runtime.poll_paused:
            return True

        now = time.monotonic()
        # 暂停轮询期间，仅在到达重试窗口后放行一次探测请求。
        if now < self._poll_runtime.next_poll_retry_at or self._poll_probe_in_progress:
            return False

        self._poll_probe_in_progress = True
        return True

    def finish_poll_attempt(self):
        if self._poll_probe_in_progress:
            self._poll_probe_in_progress = False

    def mark_poll_success(self):
        # 任意一次读成功即视为链路恢复，清空熔断与退避状态。
        if self._poll_runtime.poll_paused:
            _LOGGER.warning("Modbus communication recovered on %s, resume polling", self.hub_name)
        self._poll_runtime.poll_paused = False
        self._poll_runtime.next_poll_retry_at = 0.0
        self._poll_runtime.next_poll_retry_wall = None
        self._poll_runtime.last_recovered_at = datetime.now()
        self._poll_runtime.error_count = 0
        self.error = 0

    def exception(self):
        self.error += 1
        now = time.monotonic()
        # 线性退避：失败次数越多重试间隔越长，但不超过上限。
        delay = min(self._max_poll_retry_seconds, self._poll_retry_seconds * max(1, self.error))

        if not self._poll_runtime.poll_paused:
            _LOGGER.warning(
                "Modbus communication failed on %s, pause polling and retry in %ss",
                self.hub_name,
                delay,
            )

        self._poll_runtime.poll_paused = True
        self._poll_runtime.error_count = self.error
        self._poll_runtime.next_poll_retry_at = now + delay
        self._poll_runtime.next_poll_retry_wall = datetime.now() + timedelta(seconds=delay)
        self._poll_runtime.last_error_at = datetime.now()

        if self._reconnect_pending or now < self._next_reconnect_at:
            return

        self._reconnect_pending = True
        from homeassistant.helpers.event import async_call_later
        async_call_later(self.hass, 2, self.reconnect)

    def reg_basic_info(self, reg, index):
        """提取寄存器访问所需的基础参数。"""
        register_type = reg.get(CONF_REGISTER_TYPE)
        register = reg[CONF_REGISTER] if index == -1 else reg[CONF_REGISTERS][index]
        slave = reg.get(CONF_SLAVE, 1)
        scale = reg.get(CONF_SCALE, 1)
        offset = reg.get(CONF_OFFSET, 0)
        return (register_type, slave, register, scale, offset)

    async def read_value(self, index, prop):
        """从 Modbus 读取指定属性并按 scale/offset 转换。"""
        reg = self.regs[prop]
        register_type, slave, register, scale, offset = self.reg_basic_info(reg, index)
        count = reg.get(CONF_COUNT, 1)

        async with self._io_lock:
            if register_type == REGISTER_TYPE_COIL:
                result = await self.hub.async_pb_call(slave, register, count, CALL_TYPE_COIL)
                return bool(result.bits[0])

            if register_type == REGISTER_TYPE_INPUT:
                result = await self.hub.async_pb_call(slave, register, count, CALL_TYPE_REGISTER_INPUT)
            else:
                result = await self.hub.async_pb_call(slave, register, count, CALL_TYPE_REGISTER_HOLDING)

        registers = result.registers
        if reg.get(CONF_REVERSE_ORDER):
            registers.reverse()

        byte_string = b"".join([x.to_bytes(2, byteorder="big") for x in registers])
        val = struct.unpack(reg[CONF_STRUCTURE], byte_string)[0]
        return scale * val + offset

    async def write_value(self, index, prop, value):
        """向 Modbus 写入指定属性值。"""
        reg = self.regs[prop]
        register_type, slave, register, scale, offset = self.reg_basic_info(reg, index)

        async with self._io_lock:
            if register_type == REGISTER_TYPE_COIL:
                await self.hass.services.async_call(
                    "modbus",
                    "write_coil",
                    {
                        "hub": self.hub_name,
                        "slave": slave,
                        "address": register,
                        "state": bool(value),
                    },
                    blocking=True,
                )
            else:
                val = int((value - offset) / scale)
                await self.hass.services.async_call(
                    "modbus",
                    "write_register",
                    {
                        "hub": self.hub_name,
                        "slave": slave,
                        "address": register,
                        "value": [val],
                    },
                    blocking=True,
                )


class ZhiModbusClimate(ClimateEntity):
    """Home Assistant 温控实体实现。"""

    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, bus, name, index=-1):
        self._bus = bus
        self._name = name
        self._index = index
        self._values = {}
        self._last_on_operation = None
        self._skip_update = False

        self._pending_hvac_mode = None
        self._pending_target_temperature = None
        self._pending_hvac_until = None
        self._pending_target_temperature_until = None

        features = ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        for prop in self._bus.regs:
            features |= SUPPORTED_FEATURES[prop]
        self._attr_supported_features = features

    def _pending_valid(self, until_value):
        """判断写入后的临时状态是否仍在有效期。"""
        return until_value is not None and datetime.now() < until_value

    def _set_pending_hvac(self, mode):
        self._pending_hvac_mode = mode
        self._pending_hvac_until = datetime.now() + timedelta(seconds=PENDING_SECONDS)

    @property
    def unique_id(self):
        from homeassistant.util import slugify
        return self.__class__.__name__.lower() + "." + slugify(self.name)

    @property
    def name(self):
        return self._name

    @property
    def temperature_unit(self):
        return self._bus.unit

    @property
    def target_temperature_step(self):
        return 1

    @property
    def current_temperature(self):
        return self.get_value(REG_TEMPERATURE)

    @property
    def target_temperature(self):
        real_value = self.get_value(REG_TARGET_TEMPERATURE)
        pending_value = self._pending_target_temperature
        # 写入后短时间优先展示 pending 值，避免设备回读延迟引起界面跳变。
        if pending_value is not None and self._pending_valid(self._pending_target_temperature_until):
            if real_value == pending_value:
                self._pending_target_temperature = None
                self._pending_target_temperature_until = None
                return real_value
            return pending_value

        self._pending_target_temperature = None
        self._pending_target_temperature_until = None
        if real_value is not None:
            return real_value

        return None

    @property
    def current_humidity(self):
        return self.get_value(REG_HUMIDITY)

    @property
    def target_humidity(self):
        return self.get_value(REG_TARGET_HUMIDITY)

    @property
    def hvac_action(self):
        return HVAC_ACTIONS[self.hvac_mode]

    @property
    def hvac_mode(self):
        real_mode = None
        if REG_HVAC_OFF in self._bus.regs:
            off_value = self.get_value(REG_HVAC_OFF)
            if off_value == self._bus.hvac_off_value:
                real_mode = HVACMode.OFF

        if real_mode is None:
            hvac_mode = self.get_mode(self._bus.hvac_modes, REG_HVAC_MODE)
            if hvac_mode is not None:
                if hvac_mode != HVACMode.OFF:
                    self._last_on_operation = hvac_mode
                real_mode = hvac_mode

        pending_mode = self._pending_hvac_mode
        # 模式切换后短时间优先展示 pending 值，提升交互一致性。
        if pending_mode is not None and self._pending_valid(self._pending_hvac_until):
            if real_mode == pending_mode:
                self._pending_hvac_mode = None
                self._pending_hvac_until = None
                return real_mode
            return pending_mode

        self._pending_hvac_mode = None
        self._pending_hvac_until = None
        if real_mode is not None:
            return real_mode

        return self._last_on_operation or HVACMode.OFF

    @property
    def hvac_modes(self):
        return [HVACMode.OFF] + list(self._bus.hvac_modes)

    @property
    def fan_mode(self):
        return self.get_mode(self._bus.fan_modes, REG_FAN_MODE)

    @property
    def fan_modes(self):
        return list(self._bus.fan_modes)

    @property
    def swing_mode(self):
        return self.get_mode(self._bus.swing_modes, REG_SWING_MODE)

    @property
    def swing_modes(self):
        return list(self._bus.swing_modes)

    @property
    def preset_mode(self):
        return self.get_value(REG_PRESET_MODE)

    @property
    def preset_modes(self):
        return list(self._bus.preset_modes)

    @property
    def is_aux_heat(self):
        return self.get_value(REG_AUX_HEAT) == self._bus.aux_heat_on_value

    async def async_set_temperature(self, **kwargs):
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            self._pending_target_temperature = temperature
            self._pending_target_temperature_until = datetime.now() + timedelta(seconds=PENDING_SECONDS)
            _LOGGER.debug("Write %s: %s = %s", self.name, REG_TARGET_TEMPERATURE, temperature)
            await self._bus.write_value(self._index, REG_TARGET_TEMPERATURE, temperature)
            self._values[REG_TARGET_TEMPERATURE] = None
            self.async_write_ha_state()

    async def async_set_humidity(self, humidity):
        await self.set_value(REG_TARGET_HUMIDITY, humidity)

    async def async_set_hvac_mode(self, hvac_mode):
        if REG_HVAC_OFF in self._bus.regs:
            # 兼容部分设备使用独立开关寄存器控制开/关机。
            await self.set_value(
                REG_HVAC_OFF,
                self._bus.hvac_off_value if hvac_mode == HVACMode.OFF else self._bus.hvac_on_value,
            )

            if hvac_mode == HVACMode.OFF:
                self._set_pending_hvac(HVACMode.OFF)
                self._values[REG_HVAC_OFF] = None
                if REG_HVAC_MODE in self._bus.regs:
                    self._values[REG_HVAC_MODE] = None
                self.async_write_ha_state()
                return

        if hvac_mode not in self._bus.hvac_modes:
            best_hvac_mode = self.best_hvac_mode
            _LOGGER.warning("Fix operation mode from %s to %s", hvac_mode, best_hvac_mode)
            hvac_mode = best_hvac_mode

        self._set_pending_hvac(hvac_mode)
        self._last_on_operation = hvac_mode

        await self.set_mode(self._bus.hvac_modes, REG_HVAC_MODE, hvac_mode)
        if REG_HVAC_OFF in self._bus.regs:
            self._values[REG_HVAC_OFF] = None
        self._values[REG_HVAC_MODE] = None
        self.async_write_ha_state()

    @property
    def best_hvac_mode(self):
        for mode in (HVACMode.HEAT_COOL, HVACMode.COOL, HVACMode.HEAT):
            if mode in self._bus.hvac_modes:
                return mode
        return None

    async def async_turn_on(self):
        _LOGGER.warning("Turn on %s", self.name)
        if REG_HVAC_OFF in self._bus.regs:
            await self.set_value(REG_HVAC_OFF, self._bus.hvac_on_value)
            self._values[REG_HVAC_OFF] = None
        on_mode = self._last_on_operation or self.best_hvac_mode or next(iter(self._bus.hvac_modes), HVACMode.OFF)
        self._set_pending_hvac(on_mode)
        if REG_HVAC_MODE in self._bus.regs:
            self._values[REG_HVAC_MODE] = None
        self.async_write_ha_state()

    async def async_turn_off(self):
        _LOGGER.warning("Turn off %s", self.name)
        if REG_HVAC_OFF in self._bus.regs:
            await self.set_value(REG_HVAC_OFF, self._bus.hvac_off_value)
            self._values[REG_HVAC_OFF] = None
        self._set_pending_hvac(HVACMode.OFF)
        if REG_HVAC_MODE in self._bus.regs:
            self._values[REG_HVAC_MODE] = None
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode):
        if fan_mode in self._bus.fan_modes:
            value = self._bus.fan_modes[fan_mode]
            await self._bus.write_value(self._index, REG_FAN_MODE, value)
            self._values[REG_FAN_MODE] = value
            self.async_write_ha_state()
            return
        _LOGGER.error("Invalid fan mode %s for %s/%s", fan_mode, self._name, REG_FAN_MODE)

    async def async_set_swing_mode(self, swing_mode):
        await self.set_mode(self._bus.swing_modes, REG_SWING_MODE, swing_mode)

    async def async_set_preset_mode(self, preset_mode):
        await self.set_value(REG_PRESET_MODE, preset_mode)

    async def async_turn_aux_heat_on(self):
        await self.set_value(REG_AUX_HEAT, self._bus.aux_heat_on_value)

    async def async_turn_aux_heat_off(self):
        await self.set_value(REG_AUX_HEAT, self._bus.aux_heat_off_value)

    async def async_update(self):
        if self._skip_update:
            self._skip_update = False
            _LOGGER.debug("Skip update on %s", self._name)
            return

        # 通讯不稳定时由总线熔断机制节流轮询，避免持续刷错。
        if not self._bus.should_poll():
            self._attr_available = False
            return

        try:
            for prop in self._bus.regs:
                if prop == REG_FAN_MODE:
                    continue

                self._values[prop] = await self._bus.read_value(self._index, prop)
        except Exception:
            self._attr_available = False
            self._bus.exception()
            _LOGGER.debug("Exception %d on %s", self._bus.error, self._name)
            return
        finally:
            # 无论成功或失败都释放探测状态，避免后续重试被阻塞。
            self._bus.finish_poll_attempt()

        self._bus.mark_poll_success()
        self._attr_available = True

    def get_value(self, prop):
        return self._values.get(prop)

    async def set_value(self, prop, value):
        _LOGGER.debug("Write %s: %s = %s", self.name, prop, value)
        await self._bus.write_value(self._index, prop, value)
        self._values[prop] = value

    def get_mode(self, modes, prop):
        value = self.get_value(prop)
        if value is None:
            return None

        for k, v in modes.items():
            if v == value:
                return k

        _LOGGER.error("Invalid value %s for %s/%s", value, self._name, prop)
        return None

    async def set_mode(self, modes, prop, mode):
        if mode in modes:
            await self.set_value(prop, modes[mode])
            return
        _LOGGER.error("Invalid mode %s for %s/%s", mode, self._name, prop)

"""Expose selected climate entities to HomeKit with standard fan-mode names."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    PLATFORM_SCHEMA,
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import CONF_NAME, UnitOfTemperature
from homeassistant.core import Event, HomeAssistant, State, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .mapping import HOMEKIT_FAN_MODES, from_source, to_source

CONF_SOURCE_ENTITY_ID = "source_entity_id"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_NAME): cv.string,
        vol.Required(CONF_SOURCE_ENTITY_ID): cv.entity_id,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict[str, Any],
    async_add_entities: AddEntitiesCallback,
    discovery_info: Any = None,
) -> None:
    """Add one proxy per configured source climate entity."""
    async_add_entities(
        [HomeKitClimateProxy(config[CONF_NAME], config[CONF_SOURCE_ENTITY_ID])]
    )


class HomeKitClimateProxy(ClimateEntity):
    """Present three standard speeds while preserving the source's six speeds."""

    _attr_should_poll = False
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_fan_modes = list(HOMEKIT_FAN_MODES)

    def __init__(self, name: str, source_entity_id: str) -> None:
        self._attr_name = name
        self._attr_unique_id = f"homekit_climate_proxy_{source_entity_id}"
        self._source_entity_id = source_entity_id
        self._attr_available = False
        self._attr_hvac_modes = [HVACMode.OFF]

    async def async_added_to_hass(self) -> None:
        """Mirror source state without adding Modbus polling or writes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, [self._source_entity_id], self._source_changed
            )
        )
        self._sync_from_source(self.hass.states.get(self._source_entity_id))
        self.async_write_ha_state()

    @callback
    def _source_changed(self, event: Event) -> None:
        self._sync_from_source(event.data.get("new_state"))
        self.async_write_ha_state()

    @callback
    def _sync_from_source(self, source: State | None) -> None:
        if source is None or source.state in ("unknown", "unavailable"):
            self._attr_available = False
            return

        self._attr_available = True
        attrs = source.attributes
        self._attr_hvac_mode = HVACMode(source.state)
        self._attr_hvac_modes = [HVACMode(mode) for mode in attrs["hvac_modes"]]
        self._attr_current_temperature = attrs.get("current_temperature")
        self._attr_target_temperature = attrs.get("temperature")
        self._attr_fan_mode = from_source(attrs.get("fan_mode"))
        if (min_temp := attrs.get("min_temp")) is not None:
            self._attr_min_temp = min_temp
        if (max_temp := attrs.get("max_temp")) is not None:
            self._attr_max_temp = max_temp
        if (step := attrs.get("target_temp_step")) is not None:
            self._attr_target_temperature_step = step

    async def _forward(self, service: str, **data: Any) -> None:
        await self.hass.services.async_call(
            "climate",
            service,
            {"entity_id": self._source_entity_id, **data},
            blocking=True,
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        await self._forward("set_fan_mode", **{ATTR_FAN_MODE: to_source(fan_mode)})

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        await self._forward("set_hvac_mode", **{ATTR_HVAC_MODE: hvac_mode})

    async def async_set_temperature(self, **kwargs: Any) -> None:
        data = {key: kwargs[key] for key in (ATTR_TEMPERATURE, ATTR_HVAC_MODE) if key in kwargs}
        await self._forward("set_temperature", **data)

    async def async_turn_on(self) -> None:
        await self._forward("turn_on")

    async def async_turn_off(self) -> None:
        await self._forward("turn_off")

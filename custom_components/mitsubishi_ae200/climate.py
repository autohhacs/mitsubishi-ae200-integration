"""Climate platform for AutoH Mitsubishi AE200 integration."""
import logging

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACMode,
    ClimateEntityFeature,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class TestClimate(ClimateEntity):
    """Test climate entity to verify the integration works."""

    def __init__(self, name: str, config_data: dict):
        """Initialize the climate entity."""
        self._name = f"AutoH {name}"
        self._config_data = config_data
        self._current_temperature = 20.0
        self._target_temperature = 22.0
        self._hvac_mode = HVACMode.OFF

    @property
    def name(self):
        """Return the name of the climate entity."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of temperature measurement."""
        if self._config_data.get("temperature_unit") == "fahrenheit":
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._config_data.get("temperature_unit") == "fahrenheit":
            return (self._current_temperature * 9/5) + 32
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the target temperature."""
        if self._config_data.get("temperature_unit") == "fahrenheit":
            return (self._target_temperature * 9/5) + 32
        return self._target_temperature

    @property
    def hvac_mode(self):
        """Return current HVAC mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return available HVAC modes."""
        return [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]

    @property
    def supported_features(self):
        """Return supported features."""
        return ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def min_temp(self):
        """Return minimum temperature."""
        if self._config_data.get("temperature_unit") == "fahrenheit":
            return 61  # 16°C
        return 16

    @property
    def max_temp(self):
        """Return maximum temperature."""
        if self._config_data.get("temperature_unit") == "fahrenheit":
            return 86  # 30°C
        return 30

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get("temperature")
        if temperature is not None:
            # Convert from display unit to Celsius for storage
            if self._config_data.get("temperature_unit") == "fahrenheit":
                self._target_temperature = (temperature - 32) * 5/9
            else:
                self._target_temperature = temperature
            
            _LOGGER.info(f"Setting temperature to {temperature} for {self._name}")
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new HVAC mode."""
        self._hvac_mode = hvac_mode
        _LOGGER.info(f"Setting HVAC mode to {hvac_mode} for {self._name}")
        self.async_write_ha_state()


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities from config entry."""
    _LOGGER.info("Setting up AutoH Mitsubishi AE200 climate entities...")

    config_data = hass.data[DOMAIN][config_entry.entry_id]
    controller_id = config_data.get("controller_id", "unknown")

    # For now, create a test entity
    # Later we'll replace this with real device discovery
    entities = [
        TestClimate(f"Test Device ({controller_id})", config_data)
    ]

    async_add_entities(entities, update_before_add=False)
    _LOGGER.info(f"Added {len(entities)} test climate entity(ies)")

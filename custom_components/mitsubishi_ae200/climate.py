"""Minimal climate platform."""
import logging
from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode, ClimateEntityFeature
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE

_LOGGER = logging.getLogger(__name__)
DOMAIN = "mitsubishi_ae200"

class TestClimate(ClimateEntity):
    def __init__(self, name):
        self._name = name
        self._current_temperature = 70
        self._target_temperature = 72
        self._hvac_mode = HVACMode.COOL

    @property
    def name(self):
        return self._name

    @property
    def temperature_unit(self):
        return UnitOfTemperature.FAHRENHEIT

    @property
    def current_temperature(self):
        return self._current_temperature

    @property
    def target_temperature(self):
        return self._target_temperature

    @property
    def hvac_mode(self):
        return self._hvac_mode

    @property
    def hvac_modes(self):
        return [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]

    @property
    def supported_features(self):
        return ClimateEntityFeature.TARGET_TEMPERATURE

    @property
    def min_temp(self):
        return 60

    @property
    def max_temp(self):
        return 85

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp:
            _LOGGER.info(f"TEST: Setting {self._name} to {temp}°F")
            self._target_temperature = temp
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        _LOGGER.info(f"TEST: Setting {self._name} mode to {hvac_mode}")
        self._hvac_mode = hvac_mode
        self.async_write_ha_state()

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up test climate."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    name = config.get("name", "Test")
    
    _LOGGER.info(f"Creating test climate entity: {name}")
    
    entities = [TestClimate(f"AE200 {name}")]
    async_add_entities(entities)
    
    _LOGGER.info("Test climate entity created successfully")

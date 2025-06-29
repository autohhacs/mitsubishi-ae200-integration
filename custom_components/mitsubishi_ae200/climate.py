"""Climate platform for AutoH Mitsubishi AE200 integration."""
import logging
import asyncio

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACMode,
    ClimateEntityFeature,
)
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DOMAIN,
    CONF_CONTROLLER_ID,
    CONF_IP_ADDRESS,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_TEMPERATURE_UNIT,
    TEMP_FAHRENHEIT,
)
from .mitsubishi_ae200 import MitsubishiAE200Functions

_LOGGER = logging.getLogger(__name__)

MIN_TEMP_C = 16
MAX_TEMP_C = 30
MIN_TEMP_F = 61  # 16°C converted to F
MAX_TEMP_F = 86  # 30°C converted to F


def celsius_to_fahrenheit(celsius):
    """Convert Celsius to Fahrenheit."""
    if celsius is None:
        return None
    return round((celsius * 9/5) + 32, 1)


def fahrenheit_to_celsius(fahrenheit):
    """Convert Fahrenheit to Celsius."""
    if fahrenheit is None:
        return None
    return round((fahrenheit - 32) * 5/9, 1)


class Mode:
    """HVAC Mode constants."""
    Heat = "HEAT"
    Dry = "DRY"
    Cool = "COOL"
    Fan = "FAN"
    Auto = "AUTO"


class AE200Device:
    """Represent an AE200 device."""

    def __init__(self, ipaddress: str, deviceid: str, name: str, 
                 mitsubishi_ae200_functions: MitsubishiAE200Functions, 
                 username: str, password: str):
        """Initialize the device."""
        self._ipaddress = ipaddress
        self._deviceid = deviceid
        self._name = name
        self._mitsubishi_ae200_functions = mitsubishi_ae200_functions
        self._username = username
        self._password = password
        self._attributes = {}
        self._last_info_time_s = 0
        self._info_lease_seconds = 30

    async def _refresh_device_info_async(self):
        """Refresh device information from the controller."""
        _LOGGER.debug(f"Refreshing device info: {self._ipaddress} - {self._deviceid} ({self._name})")
        try:
            self._attributes = await self._mitsubishi_ae200_functions.getDeviceInfoAsync(
                self._ipaddress, self._deviceid, self._username, self._password
            )
            self._last_info_time_s = asyncio.get_event_loop().time()
            _LOGGER.debug(f"Device {self._deviceid} attributes: {self._attributes}")
        except Exception as e:
            _LOGGER.error(f"Failed to refresh device info for {self._deviceid}: {e}")

    async def _get_info(self, key, default_value):
        """Get device information, refreshing if needed."""
        current_time = asyncio.get_event_loop().time()
        if not self._attributes or (current_time - self._last_info_time_s) > self._info_lease_seconds:
            await self._refresh_device_info_async()
        return self._attributes.get(key, default_value)

    async def _to_float(self, value):
        """Convert value to float safely."""
        try:
            return float(value) if value is not None and str(value).strip() != "" else None
        except (ValueError, TypeError):
            return None

    def getName(self):
        """Get device name."""
        return self._name

    async def getTargetTemperature(self):
        """Get target temperature based on current mode."""
        try:
            mode = await self.getMode()
            if mode == Mode.Heat:
                return await self._to_float(await self._get_info("SetTemp2", None))
            elif mode in [Mode.Cool, Mode.Dry]:
                return await self._to_float(await self._get_info("SetTemp1", None))
            else:
                return await self._to_float(await self._get_info("SetTemp1", None))
        except Exception as e:
            _LOGGER.error(f"Error getting target temperature for device {self._deviceid}: {e}")
            return None

    async def getRoomTemperature(self):
        """Get current room temperature."""
        try:
            return await self._to_float(await self._get_info("InletTemp", None))
        except Exception as e:
            _LOGGER.error(f"Error getting room temperature for device {self._deviceid}: {e}")
            return None

    async def getMode(self):
        """Get current operating mode."""
        try:
            return await self._get_info("Mode", Mode.Auto)
        except Exception as e:
            _LOGGER.error(f"Error getting mode for device {self._deviceid}: {e}")
            return Mode.Auto

    async def isPowerOn(self):
        """Check if device is powered on."""
        try:
            drive_status = await self._get_info("Drive", "OFF")
            return drive_status == "ON"
        except Exception as e:
            _LOGGER.error(f"Error getting power status for device {self._deviceid}: {e}")
            return False

    async def setTemperature(self, temperature):
        """Set target temperature based on current mode."""
        try:
            mode = await self.getMode()
            temp_str = str(int(round(temperature)))
            
            if mode == Mode.Heat:
                await self._mitsubishi_ae200_functions.sendAsync(
                    self._ipaddress, self._deviceid, {"SetTemp2": temp_str}, 
                    self._username, self._password
                )
            else:
                await self._mitsubishi_ae200_functions.sendAsync(
                    self._ipaddress, self._deviceid, {"SetTemp1": temp_str}, 
                    self._username, self._password
                )
            _LOGGER.info(f"Set temperature to {temperature}°C for device {self._deviceid} in {mode} mode")
            self._last_info_time_s = 0  # Force refresh
        except Exception as e:
            _LOGGER.error(f"Failed to set temperature for device {self._deviceid}: {e}")
            raise

    async def setMode(self, mode):
        """Set operating mode."""
        try:
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Mode": mode}, 
                self._username, self._password
            )
            _LOGGER.info(f"Set mode to {mode} for device {self._deviceid}")
            self._last_info_time_s = 0  # Force refresh
        except Exception as e:
            _LOGGER.error(f"Failed to set mode for device {self._deviceid}: {e}")
            raise

    async def powerOn(self):
        """Turn on the device."""
        try:
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Drive": "ON"}, 
                self._username, self._password
            )
            _LOGGER.info(f"Powered on device {self._deviceid}")
            self._last_info_time_s = 0  # Force refresh
        except Exception as e:
            _LOGGER.error(f"Failed to power on device {self._deviceid}: {e}")
            raise

    async def powerOff(self):
        """Turn off the device."""
        try:
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Drive": "OFF"}, 
                self._username, self._password
            )
            _LOGGER.info(f"Powered off device {self._deviceid}")
            self._last_info_time_s = 0  # Force refresh
        except Exception as e:
            _LOGGER.error(f"Failed to power off device {self._deviceid}: {e}")
            raise


class AE200Climate(ClimateEntity):
    """Representation of an AE200 climate device."""

    def __init__(self, hass, device: AE200Device, controllerid: str, use_fahrenheit: bool = False):
        """Initialize the climate entity."""
        self._device = device
        self._use_fahrenheit = use_fahrenheit
        self._attr_unique_id = f"mitsubishi_ae200_{controllerid}_{device._deviceid}"
        self._attr_name = f"AutoH {device.getName()}"
        
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
            HVACMode.HEAT_COOL,
        ]
        
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | 
            ClimateEntityFeature.TURN_ON |
            ClimateEntityFeature.TURN_OFF
        )
        self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT if use_fahrenheit else UnitOfTemperature.CELSIUS
        self._current_temperature = None
        self._target_temperature = None
        self._hvac_mode = HVACMode.OFF
        self._last_hvac_mode = HVACMode.COOL

    @property
    def unique_id(self):
        """Return unique ID for this entity."""
        return self._attr_unique_id

    @property
    def name(self):
        """Return the name of the climate entity."""
        return self._attr_name

    @property
    def temperature_unit(self):
        """Return the temperature unit."""
        return self._attr_temperature_unit

    @property
    def current_temperature(self):
        """Return the current temperature."""
        if self._current_temperature is None:
            return None
        return celsius_to_fahrenheit(self._current_temperature) if self._use_fahrenheit else self._current_temperature

    @property
    def target_temperature(self):
        """Return the target temperature."""
        if self._target_temperature is None:
            return None
        return celsius_to_fahrenheit(self._target_temperature) if self._use_fahrenheit else self._target_temperature

    @property
    def min_temp(self):
        """Return minimum temperature."""
        return MIN_TEMP_F if self._use_fahrenheit else MIN_TEMP_C

    @property
    def max_temp(self):
        """Return maximum temperature."""
        return MAX_TEMP_F if self._use_fahrenheit else MAX_TEMP_C

    @property
    def hvac_mode(self):
        """Return current HVAC mode."""
        return self._hvac_mode

    @property
    def hvac_modes(self):
        """Return available HVAC modes."""
        return self._attr_hvac_modes

    @property
    def supported_features(self):
        """Return supported features."""
        return self._attr_supported_features

    async def async_turn_on(self):
        """Turn on the HVAC."""
        _LOGGER.info(f"Turning on HVAC mode: {self._last_hvac_mode} for {self.name}")
        try:
            await self._device.powerOn()
            self._hvac_mode = self._last_hvac_mode
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to turn on HVAC for {self.name}: {e}")

    async def async_turn_off(self):
        """Turn off the HVAC."""
        _LOGGER.info(f"Turning off HVAC for {self.name}")
        try:
            await self._device.powerOff()
            self._hvac_mode = HVACMode.OFF
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to turn off HVAC for {self.name}: {e}")

    async def async_set_temperature(self, **kwargs):
        """Set temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            _LOGGER.info(f"Setting temperature: {temperature} for {self.name}")
            try:
                temp_celsius = fahrenheit_to_celsius(temperature) if self._use_fahrenheit else temperature
                await self._device.setTemperature(temp_celsius)
                self._target_temperature = temp_celsius
                self.async_write_ha_state()
            except Exception as e:
                _LOGGER.error(f"Failed to set temperature for {self.name}: {e}")

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode."""
        _LOGGER.info(f"Setting HVAC mode: {hvac_mode} for {self.name}")
        try:
            if hvac_mode == HVACMode.OFF:
                await self._device.powerOff()
                self._hvac_mode

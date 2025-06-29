import logging
import asyncio

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    HVACMode,
    ClimateEntityFeature,
)
from homeassistant.const import (
    UnitOfTemperature,
    ATTR_TEMPERATURE,
)
from homeassistant.helpers.entity import generate_entity_id
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
    Heat = "HEAT"
    Dry = "DRY"
    Cool = "COOL"
    Fan = "FAN"
    Auto = "AUTO"


class AE200Device:
    def __init__(self, ipaddress: str, deviceid: str, name: str, 
                 mitsubishi_ae200_functions: MitsubishiAE200Functions, 
                 username: str, password: str):
        self._ipaddress = ipaddress
        self._deviceid = deviceid
        self._name = name
        self._mitsubishi_ae200_functions = mitsubishi_ae200_functions
        self._username = username
        self._password = password
        self._attributes = {}
        self._last_info_time_s = 0
        self._info_lease_seconds = 10

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
            raise

    async def _get_info(self, key, default_value):
        """Get device information, refreshing if needed."""
        if not self._attributes or (asyncio.get_event_loop().time() - self._last_info_time_s) > self._info_lease_seconds:
            await self._refresh_device_info_async()
        return self._attributes.get(key, default_value)

    async def _to_float(self, value):
        """Convert value to float safely."""
        try:
            return float(value) if value is not None and value != "" else None
        except (ValueError, TypeError):
            return None

    async def getID(self):
        return self._deviceid

    def getName(self):
        return self._name

    async def getTargetTemperature(self):
        """Get target temperature based on current mode."""
        mode = await self.getMode()
        if mode == Mode.Heat:
            return await self._to_float(await self._get_info("SetTemp2", None))
        elif mode in [Mode.Cool, Mode.Dry]:
            return await self._to_float(await self._get_info("SetTemp1", None))
        else:
            # For Auto mode, return the cooling setpoint as primary
            return await self._to_float(await self._get_info("SetTemp1", None))
        
    async def getTargetTemperatureHigh(self):
        """Get high temperature setpoint (cooling)."""
        return await self._to_float(await self._get_info("SetTemp1", None))
    
    async def getTargetTemperatureLow(self):
        """Get low temperature setpoint (heating)."""
        return await self._to_float(await self._get_info("SetTemp2", None))

    async def getRoomTemperature(self):
        """Get current room temperature."""
        return await self._to_float(await self._get_info("InletTemp", None))

    async def getFanSpeed(self):
        """Get current fan speed."""
        return await self._get_info("FanSpeed", None)
    
    async def getSwingMode(self):
        """Get current swing/air direction mode."""
        return await self._get_info("AirDirection", None)

    async def getMode(self):
        """Get current operating mode."""
        return await self._get_info("Mode", Mode.Auto)

    async def isPowerOn(self):
        """Check if device is powered on."""
        drive_status = await self._get_info("Drive", "OFF")
        return drive_status == "ON"

    async def setTemperature(self, temperature):
        """Set target temperature based on current mode."""
        mode = await self.getMode()
        temp_str = str(int(round(temperature)))  # Round to nearest integer
        
        try:
            if mode == Mode.Heat:
                await self._mitsubishi_ae200_functions.sendAsync(
                    self._ipaddress, self._deviceid, {"SetTemp2": temp_str}, 
                    self._username, self._password
                )
            else:  # Cool, Dry, or other modes
                await self._mitsubishi_ae200_functions.sendAsync(
                    self._ipaddress, self._deviceid, {"SetTemp1": temp_str}, 
                    self._username, self._password
                )
            _LOGGER.info(f"Set temperature to {temperature}°C for device {self._deviceid} in {mode} mode")
        except Exception as e:
            _LOGGER.error(f"Failed to set temperature for device {self._deviceid}: {e}")
            raise
            
    async def setTemperatureHigh(self, temperature):
        """Set high temperature setpoint (cooling)."""
        temp_str = str(int(round(temperature)))
        try:
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"SetTemp1": temp_str}, 
                self._username, self._password
            )
            _LOGGER.info(f"Set high temperature to {temperature}°C for device {self._deviceid}")
        except Exception as e:
            _LOGGER.error(f"Failed to set high temperature for device {self._deviceid}: {e}")
            raise
        
    async def setTemperatureLow(self, temperature):
        """Set low temperature setpoint (heating)."""
        temp_str = str(int(round(temperature)))
        try:
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"SetTemp2": temp_str}, 
                self._username, self._password
            )
            _LOGGER.info(f"Set low temperature to {temperature}°C for device {self._deviceid}")
        except Exception as e:
            _LOGGER.error(f"Failed to set low temperature for device {self._deviceid}: {e}")
            raise

    async def setFanSpeed(self, speed):
        """Set fan speed."""
        try:
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"FanSpeed": speed}, 
                self._username, self._password
            )
            _LOGGER.info(f"Set fan speed to {speed} for device {self._deviceid}")
        except Exception as e:
            _LOGGER.error(f"Failed to set fan speed for device {self._deviceid}: {e}")
            raise
        
    async def setSwingMode(self, mode):
        """Set swing/air direction mode."""
        try:
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"AirDirection": mode}, 
                self._username, self._password
            )
            _LOGGER.info(f"Set swing mode to {mode} for device {self._deviceid}")
        except Exception as e:
            _LOGGER.error(f"Failed to set swing mode for device {self._deviceid}: {e}")
            raise

    async def setMode(self, mode):
        """Set operating mode."""
        try:
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Mode": mode}, 
                self._username, self._password
            )
            _LOGGER.info(f"Set mode to {mode} for device {self._deviceid}")
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
        except Exception as e:
            _LOGGER.error(f"Failed to power off device {self._deviceid}: {e}")
            raise


class AE200Climate(ClimateEntity):
    def __init__(self, hass, device: AE200Device, controllerid: str, use_fahrenheit: bool = False):
        self._device = device
        self._use_fahrenheit = use_fahrenheit
        self.entity_id = generate_entity_id(
            "climate.{}", f"autoh_mitsubishi_ae_200_{controllerid}_{device.getName().lower().replace(' ', '_')}", None, hass
        )
        self._attr_hvac_modes = [
            HVACMode.OFF,
            HVACMode.HEAT,
            HVACMode.COOL,
            HVACMode.DRY,
            HVACMode.FAN_ONLY,
            HVACMode.HEAT_COOL,
        ]
        self._fan_mode_map = {
            "AUTO": "Auto",
            "LOW": "Min (1/4)",
            "MID2": "Low (2/4)",
            "MID1": "High (3/4)",
            "HIGH": "Max (4/4)",
        }
        self._reverse_fan_mode_map = {v: k for k, v in self._fan_mode_map.items()}
        self._attr_fan_modes = list(self._fan_mode_map.values())
        
        self._swing_mode_map = {
            "AUTO": "Auto",
            "SWING": "Swing",
            "VERTICAL": "Vertical",
            "MID2": "Mid 2",
            "MID1": "Mid 1",
            "MID0": "Mid 0",
            "HORIZONTAL": "Horizontal",
        }
        self._reverse_swing_mode_map = {v: k for k, v in self._swing_mode_map.items()}
        self._attr_swing_modes = list(self._swing_mode_map.values())
        
        self._attr_supported_features = (
            ClimateEntityFeature.TARGET_TEMPERATURE | 
            ClimateEntityFeature.FAN_MODE | 
            ClimateEntityFeature.SWING_MODE | 
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE |
            ClimateEntityFeature.TURN_ON |
            ClimateEntityFeature.TURN_OFF
        )
        self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT if use_fahrenheit else UnitOfTemperature.CELSIUS
        self._current_temperature = None
        self._target_temperature = None
        self._target_temperature_high = None
        self._target_temperature_low = None
        self._swing_mode = None
        self._fan_mode = None
        self._hvac_mode = HVACMode.OFF
        self._last_hvac_mode = HVACMode.COOL

    @property
    def supported_features(self):
        return self._attr_supported_features

    @property
    def should_poll(self):
        return True

    @property
    def name(self):
        return f"AutoH {self._device.getName()}"

    @property
    def temperature_unit(self):
        return self._attr_temperature_unit

    @property
    def current_temperature(self):
        if self._current

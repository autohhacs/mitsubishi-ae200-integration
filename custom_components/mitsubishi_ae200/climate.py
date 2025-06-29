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
    """Convert Celsius to Fahrenheit with proper rounding."""
    if celsius is None:
        return None
    # Use more precise conversion and round to nearest integer
    fahrenheit = (celsius * 9.0/5.0) + 32.0
    return round(fahrenheit)


def fahrenheit_to_celsius(fahrenheit):
    """Convert Fahrenheit to Celsius with proper rounding."""
    if fahrenheit is None:
        return None
    # Use more precise conversion and round to nearest integer  
    celsius = (fahrenheit - 32.0) * 5.0/9.0
    return round(celsius)


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
        self._info_lease_seconds = 15  # Reduced for more frequent updates

    async def _refresh_device_info_async(self):
        """Refresh device information from the controller."""
        _LOGGER.debug(f"Refreshing device info: {self._ipaddress} - {self._deviceid} ({self._name})")
        try:
            self._attributes = await self._mitsubishi_ae200_functions.getDeviceInfoAsync(
                self._ipaddress, self._deviceid, self._username, self._password
            )
            self._last_info_time_s = asyncio.get_event_loop().time()
            _LOGGER.info(f"Device {self._deviceid} ({self._name}) raw attributes: {self._attributes}")
        except Exception as e:
            _LOGGER.error(f"Failed to refresh device info for {self._deviceid}: {e}")
            raise

    async def _get_info(self, key, default_value):
        """Get device information, refreshing if needed."""
        current_time = asyncio.get_event_loop().time()
        if not self._attributes or (current_time - self._last_info_time_s) > self._info_lease_seconds:
            await self._refresh_device_info_async()
        value = self._attributes.get(key, default_value)
        _LOGGER.debug(f"Device {self._deviceid} - {key}: {value}")
        return value

    async def _to_float(self, value):
        """Convert value to float safely."""
        try:
            if value is None or str(value).strip() == "":
                return None
            result = float(value)
            _LOGGER.debug(f"Converted '{value}' to float: {result}")
            return result
        except (ValueError, TypeError) as e:
            _LOGGER.warning(f"Could not convert '{value}' to float: {e}")
            return None

    def getName(self):
        """Get device name."""
        return self._name

    async def getTargetTemperature(self):
        """Get target temperature based on current mode."""
        try:
            mode = await self.getMode()
            _LOGGER.info(f"Device {self._deviceid} is in {mode} mode")
            
            if mode == Mode.Heat:
                temp = await self._to_float(await self._get_info("SetTemp2", None))
                _LOGGER.info(f"Device {self._deviceid} heating target temp: {temp}")
                return temp
            elif mode in [Mode.Cool, Mode.Dry]:
                temp = await self._to_float(await self._get_info("SetTemp1", None))
                _LOGGER.info(f"Device {self._deviceid} cooling target temp: {temp}")
                return temp
            else:
                temp = await self._to_float(await self._get_info("SetTemp1", None))
                _LOGGER.info(f"Device {self._deviceid} default target temp: {temp}")
                return temp
        except Exception as e:
            _LOGGER.error(f"Error getting target temperature for device {self._deviceid}: {e}")
            return None

    async def getRoomTemperature(self):
        """Get current room temperature."""
        try:
            temp = await self._to_float(await self._get_info("InletTemp", None))
            _LOGGER.info(f"Device {self._deviceid} current room temp: {temp}")
            return temp
        except Exception as e:
            _LOGGER.error(f"Error getting room temperature for device {self._deviceid}: {e}")
            return None

    async def getMode(self):
        """Get current operating mode."""
        try:
            mode = await self._get_info("Mode", Mode.Auto)
            _LOGGER.info(f"Device {self._deviceid} mode: {mode}")
            return mode
        except Exception as e:
            _LOGGER.error(f"Error getting mode for device {self._deviceid}: {e}")
            return Mode.Auto

    async def isPowerOn(self):
        """Check if device is powered on."""
        try:
            drive_status = await self._get_info("Drive", "OFF")
            is_on = drive_status == "ON"
            _LOGGER.info(f"Device {self._deviceid} power status: {drive_status} (is_on: {is_on})")
            return is_on
        except Exception as e:
            _LOGGER.error(f"Error getting power status for device {self._deviceid}: {e}")
            return False

    async def setTemperature(self, temperature):
        """Set target temperature based on current mode."""
        try:
            mode = await self.getMode()
            # Convert to integer (AE200 expects integer values)
            temp_int = int(round(temperature))
            temp_str = str(temp_int)
            
            _LOGGER.info(f"Setting temperature for device {self._deviceid}: {temperature} -> {temp_int} in {mode} mode")
            
            if mode == Mode.Heat:
                _LOGGER.info(f"Sending SetTemp2={temp_str} to device {self._deviceid}")
                await self._mitsubishi_ae200_functions.sendAsync(
                    self._ipaddress, self._deviceid, {"SetTemp2": temp_str}, 
                    self._username, self._password
                )
            else:
                _LOGGER.info(f"Sending SetTemp1={temp_str} to device {self._deviceid}")
                await self._mitsubishi_ae200_functions.sendAsync(
                    self._ipaddress, self._deviceid, {"SetTemp1": temp_str}, 
                    self._username, self._password
                )
            
            _LOGGER.info(f"Successfully set temperature to {temp_int}°C for device {self._deviceid}")
            self._last_info_time_s = 0  # Force refresh on next read
            
            # Wait a moment and verify the change
            await asyncio.sleep(2)
            await self._refresh_device_info_async()
            
        except Exception as e:
            _LOGGER.error(f"Failed to set temperature for device {self._deviceid}: {e}")
            raise

    async def setMode(self, mode):
        """Set operating mode."""
        try:
            _LOGGER.info(f"Setting mode for device {self._deviceid}: {mode}")
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Mode": mode}, 
                self._username, self._password
            )
            _LOGGER.info(f"Successfully set mode to {mode} for device {self._deviceid}")
            self._last_info_time_s = 0  # Force refresh
        except Exception as e:
            _LOGGER.error(f"Failed to set mode for device {self._deviceid}: {e}")
            raise

    async def powerOn(self):
        """Turn on the device."""
        try:
            _LOGGER.info(f"Powering on device {self._deviceid}")
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Drive": "ON"}, 
                self._username, self._password
            )
            _LOGGER.info(f"Successfully powered on device {self._deviceid}")
            self._last_info_time_s = 0  # Force refresh
        except Exception as e:
            _LOGGER.error(f"Failed to power on device {self._deviceid}: {e}")
            raise

    async def powerOff(self):
        """Turn off the device."""
        try:
            _LOGGER.info(f"Powering off device {self._deviceid}")
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Drive": "OFF"}, 
                self._username, self._password
            )
            _LOGGER.info(f"Successfully powered off device {self._deviceid}")
            self._last_info_time_s = 0  # Force refresh
        except Exception as e:
            _LOGGER.error(f"Failed to power off device {self._deviceid}: {e}")
            raise


class AE200Climate(ClimateEntity):
    """Representation of an AE200 climate device."""

    def __init__(self, hass, device: AE200Device, controllerid: str, ipaddress: str, use_fahrenheit: bool = False):
        """Initialize the climate entity."""
        self._device = device
        self._use_fahrenheit = use_fahrenheit
        # Create unique ID using IP address to avoid conflicts between controllers
        ip_suffix = ipaddress.replace(".", "_").replace(":", "_")
        self._attr_unique_id = f"mitsubishi_ae200_{controllerid}_{ip_suffix}_{device._deviceid}"
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
        
        # Enable polling for this entity
        self._attr_should_poll = True

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
        if self._use_fahrenheit:
            return celsius_to_fahrenheit(self._current_temperature)
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the target temperature."""
        if self._target_temperature is None:
            return None
        if self._use_fahrenheit:
            return celsius_to_fahrenheit(self._target_temperature)
        return self._target_temperature

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

    @property
    def should_poll(self):
        """Return True if entity should be polled for updates."""
        return True

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
            _LOGGER.info(f"Setting temperature: {temperature}°{self.temperature_unit} for {self.name}")
            try:
                # Convert to Celsius for device communication if needed
                if self._use_fahrenheit:
                    temp_celsius = fahrenheit_to_celsius(temperature)
                    _LOGGER.info(f"Converted {temperature}°F to {temp_celsius}°C")
                else:
                    temp_celsius = temperature
                
                await self._device.setTemperature(temp_celsius)
                self._target_temperature = temp_celsius
                self.async_write_ha_state()
                _LOGGER.info(f"Successfully set temperature for {self.name}")
            except Exception as e:
                _LOGGER.error(f"Failed to set temperature for {self.name}: {e}")

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode."""
        _LOGGER.info(f"Setting HVAC mode: {hvac_mode} for {self.name}")
        try:
            if hvac_mode == HVACMode.OFF:
                await self._device.powerOff()
                self._hvac_mode = HVACMode.OFF
            else:
                await self._device.powerOn()
                mode_map = {
                    HVACMode.HEAT: Mode.Heat,
                    HVACMode.COOL: Mode.Cool,
                    HVACMode.DRY: Mode.Dry,
                    HVACMode.FAN_ONLY: Mode.Fan,
                    HVACMode.HEAT_COOL: Mode.Auto,
                }
                await self._device.setMode(mode_map.get(hvac_mode, Mode.Auto))
                self._hvac_mode = hvac_mode
                self._last_hvac_mode = hvac_mode
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to set HVAC mode for {self.name}: {e}")

    async def async_update(self):
        """Update the entity state."""
        _LOGGER.debug(f"Updating climate entity: {self.name}")
        try:
            # Get current temperature
            self._current_temperature = await self._device.getRoomTemperature()
            
            # Check power status and get other attributes
            if await self._device.isPowerOn():
                self._target_temperature = await self._device.getTargetTemperature()
                mode = await self._device.getMode()
                
                # Map device mode to HA HVAC mode
                if mode == Mode.Heat:
                    self._hvac_mode = HVACMode.HEAT
                    self._last_hvac_mode = HVACMode.HEAT
                elif mode == Mode.Cool:
                    self._hvac_mode = HVACMode.COOL
                    self._last_hvac_mode = HVACMode.COOL
                elif mode == Mode.Dry:
                    self._hvac_mode = HVACMode.DRY
                    self._last_hvac_mode = HVACMode.DRY
                elif mode == Mode.Fan:
                    self._hvac_mode = HVACMode.FAN_ONLY
                    self._last_hvac_mode = HVACMode.FAN_ONLY
                    self._target_temperature = None
                elif mode == Mode.Auto:
                    self._hvac_mode = HVACMode.HEAT_COOL
                    self._last_hvac_mode = HVACMode.HEAT_COOL
                else:
                    self._hvac_mode = HVACMode.HEAT_COOL
                    self._last_hvac_mode = HVACMode.HEAT_COOL
            else:
                self._target_temperature = None
                self._hvac_mode = HVACMode.OFF
                
            _LOGGER.debug(f"Updated {self.name}: current={self._current_temperature}°C, target={self._target_temperature}°C, mode={self._hvac_mode}")
            
        except Exception as e:
            _LOGGER.error(f"Failed to update entity {self.name}: {e}")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AutoH Mitsubishi AE200 climate devices from config entry."""
    _LOGGER.info("Setting up AutoH Mitsubishi AE200 platform...")

    config = hass.data[DOMAIN][config_entry.entry_id]
    controllerid = config[CONF_CONTROLLER_ID]
    ipaddress = config[CONF_IP_ADDRESS]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    use_fahrenheit = config.get(CONF_TEMPERATURE_UNIT) == TEMP_FAHRENHEIT
    device_names = config.get("device_names", {})

    mitsubishi_ae200_functions = MitsubishiAE200Functions()
    devices = []
    
    try:
        _LOGGER.info(f"Discovering devices on controller {ipaddress}...")
        
        # Get device list from controller
        group_list = await mitsubishi_ae200_functions.getDevicesAsync(ipaddress, username, password)
        _LOGGER.info(f"Found {len(group_list)} devices: {group_list}")
        
        for group in group_list:
            device_id = group["id"]
            # Use custom name if provided, otherwise use original name
            device_name = device_names.get(device_id, group["name"])
            
            _LOGGER.info(f"Creating device: ID={device_id}, Name={device_name}")
            
            device = AE200Device(ipaddress, device_id, device_name, mitsubishi_ae200_functions, username, password)
            climate_entity = AE200Climate(hass, device, controllerid, ipaddress, use_fahrenheit)
            devices.append(climate_entity)

        if devices:
            async_add_entities(devices, update_before_add=True)
            _LOGGER.info(f"Successfully added {len(devices)} AutoH Mitsubishi AE200 device(s).")
        else:
            _LOGGER.warning("No AutoH Mitsubishi AE200 devices found on controller.")
            
    except Exception as exc:
        _LOGGER.error("Error setting up AutoH Mitsubishi AE200 devices: %s", exc, exc_info=True)

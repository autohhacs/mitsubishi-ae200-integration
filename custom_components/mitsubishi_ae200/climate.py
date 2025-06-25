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
CONF_TEMPERATURE_UNIT,
TEMP_FAHRENHEIT,
)
from .mitsubishi_ae200 import MitsubishiAE200Functions

_LOGGER = logging.getLogger(**name**)

MIN_TEMP_C = 16
MAX_TEMP_C = 30
MIN_TEMP_F = 61  # 16°C converted to F
MAX_TEMP_F = 86  # 30°C converted to F

def celsius_to_fahrenheit(celsius):
“”“Convert Celsius to Fahrenheit.”””
if celsius is None:
return None
return round((celsius * 9/5) + 32, 1)

def fahrenheit_to_celsius(fahrenheit):
“”“Convert Fahrenheit to Celsius.”””
if fahrenheit is None:
return None
return round((fahrenheit - 32) * 5/9, 1)

class Mode:
Heat = “HEAT”
Dry = “DRY”
Cool = “COOL”
Fan = “FAN”
Auto = “AUTO”

class AE200Device:
def **init**(self, ipaddress: str, deviceid: str, name: str, mitsubishi_ae200_functions: MitsubishiAE200Functions):
self._ipaddress = ipaddress
self._deviceid = deviceid
self._name = name
self._mitsubishi_ae200_functions = mitsubishi_ae200_functions
self._attributes = {}
self._last_info_time_s = 0
self._info_lease_seconds = 8

```
async def _refresh_device_info_async(self):
    _LOGGER.debug(f"Refreshing device info: {self._ipaddress} - {self._deviceid} ({self._name})")
    self._attributes = await self._mitsubishi_ae200_functions.getDeviceInfoAsync(self._ipaddress, self._deviceid)
    self._last_info_time_s = asyncio.get_event_loop().time()

async def _get_info(self, key, default_value):
    if not self._attributes or (asyncio.get_event_loop().time() - self._last_info_time_s) > self._info_lease_seconds:
        await self._refresh_device_info_async()
    return self._attributes.get(key, default_value)

async def _to_float(self, value):
    try:
        return float(value) if value is not None else None
    except Exception:
        return None

async def getID(self):
    return self._deviceid

def getName(self):
    return self._name

async def getTargetTemperature(self):
    mode = await self.getMode()
    if mode == Mode.Heat:
        return await self._to_float(await self._get_info("SetTemp2", None))
    elif mode == Mode.Cool:
        return await self._to_float(await self._get_info("SetTemp1", None))
    elif mode == Mode.Dry:
        return await self._to_float(await self._get_info("SetTemp1", None))
    else:
        return await self._to_float(await self._get_info("SetTemp1", None))
    
async def getTargetTemperatureHigh(self):
    return await self._to_float(await self._get_info("SetTemp1", None))

async def getTargetTemperatureLow(self):
    return await self._to_float(await self._get_info("SetTemp2", None))

async def getRoomTemperature(self):
    return await self._to_float(await self._get_info("InletTemp", None))

async def getFanSpeed(self):
    return await self._get_info("FanSpeed", None)

async def getSwingMode(self):
    return await self._get_info("AirDirection", None)

async def getMode(self):
    return await self._get_info("Mode", Mode.Auto)

async def isPowerOn(self):
    return await self._get_info("Drive", "OFF") == "ON"

async def setTemperature(self, temperature):
    """Set temperature using enhanced verification method."""
    _LOGGER.info(f"Setting temperature to {temperature}°C for device {self._deviceid}")
    
    mode = await self.getMode()
    
    # Determine which temperature register to use based on mode
    if mode == Mode.Heat:
        temp_key = "SetTemp2"
    elif mode == Mode.Cool:
        temp_key = "SetTemp1"
    elif mode == Mode.Dry:
        temp_key = "SetTemp1"
    else:
        temp_key = "SetTemp1"
    
    # Round temperature to one decimal place for device compatibility
    temp_value = round(float(temperature), 1)
    
    # Use the enhanced send and verify method
    success = await self._mitsubishi_ae200_functions.sendAndVerifyAsync(
        self._ipaddress,
        self._deviceid,
        {temp_key: temp_value}
    )
    
    if success:
        _LOGGER.info(f"Temperature successfully set and verified: {temp_value}°C for device {self._deviceid}")
        # Force refresh on next read
        self._last_info_time_s = 0
    else:
        _LOGGER.error(f"Failed to set temperature {temp_value}°C for device {self._deviceid}")
    
    return success
        
async def setTemperatureHigh(self, temperature):
    """Set high temperature using enhanced verification method."""
    _LOGGER.info(f"Setting high temperature to {temperature}°C for device {self._deviceid}")
    
    temp_value = round(float(temperature), 1)
    success = await self._mitsubishi_ae200_functions.sendAndVerifyAsync(
        self._ipaddress,
        self._deviceid,
        {"SetTemp1": temp_value}
    )
    
    if success:
        _LOGGER.info(f"High temperature successfully set: {temp_value}°C for device {self._deviceid}")
        self._last_info_time_s = 0
    else:
        _LOGGER.error(f"Failed to set high temperature {temp_value}°C for device {self._deviceid}")
    
    return success
    
async def setTemperatureLow(self, temperature):
    """Set low temperature using enhanced verification method."""
    _LOGGER.info(f"Setting low temperature to {temperature}°C for device {self._deviceid}")
    
    temp_value = round(float(temperature), 1)
    success = await self._mitsubishi_ae200_functions.sendAndVerifyAsync(
        self._ipaddress,
        self._deviceid,
        {"SetTemp2": temp_value}
    )
    
    if success:
        _LOGGER.info(f"Low temperature successfully set: {temp_value}°C for device {self._deviceid}")
        self._last_info_time_s = 0
    else:
        _LOGGER.error(f"Failed to set low temperature {temp_value}°C for device {self._deviceid}")
    
    return success

async def setFanSpeed(self, speed):
    """Set fan speed using enhanced verification method."""
    _LOGGER.info(f"Setting fan speed to {speed} for device {self._deviceid}")
    
    success = await self._mitsubishi_ae200_functions.sendAndVerifyAsync(
        self._ipaddress,
        self._deviceid,
        {"FanSpeed": speed}
    )
    
    if success:
        _LOGGER.info(f"Fan speed successfully set: {speed} for device {self._deviceid}")
        self._last_info_time_s = 0
    else:
        _LOGGER.error(f"Failed to set fan speed {speed} for device {self._deviceid}")
    
    return success
    
async def setSwingMode(self, mode):
    """Set swing mode using enhanced verification method."""
    _LOGGER.info(f"Setting swing mode to {mode} for device {self._deviceid}")
    
    success = await self._mitsubishi_ae200_functions.sendAndVerifyAsync(
        self._ipaddress,
        self._deviceid,
        {"AirDirection": mode}
    )
    
    if success:
        _LOGGER.info(f"Swing mode successfully set: {mode} for device {self._deviceid}")
        self._last_info_time_s = 0
    else:
        _LOGGER.error(f"Failed to set swing mode {mode} for device {self._deviceid}")
    
    return success

async def setMode(self, mode):
    """Set HVAC mode using enhanced verification method."""
    _LOGGER.info(f"Setting mode to {mode} for device {self._deviceid}")
    
    success = await self._mitsubishi_ae200_functions.sendAndVerifyAsync(
        self._ipaddress,
        self._deviceid,
        {"Mode": mode}
    )
    
    if success:
        _LOGGER.info(f"Mode successfully set: {mode} for device {self._deviceid}")
        self._last_info_time_s = 0
    else:
        _LOGGER.error(f"Failed to set mode {mode} for device {self._deviceid}")
    
    return success

async def powerOn(self):
    """Power on device using enhanced verification method."""
    _LOGGER.info(f"Powering on device {self._deviceid}")
    
    success = await self._mitsubishi_ae200_functions.sendAndVerifyAsync(
        self._ipaddress,
        self._deviceid,
        {"Drive": "ON"}
    )
    
    if success:
        _LOGGER.info(f"Device {self._deviceid} successfully powered on")
        self._last_info_time_s = 0
    else:
        _LOGGER.error(f"Failed to power on device {self._deviceid}")
    
    return success

async def powerOff(self):
    """Power off device using enhanced verification method."""
    _LOGGER.info(f"Powering off device {self._deviceid}")
    
    success = await self._mitsubishi_ae200_functions.sendAndVerifyAsync(
        self._ipaddress,
        self._deviceid,
        {"Drive": "OFF"}
    )
    
    if success:
        _LOGGER.info(f"Device {self._deviceid} successfully powered off")
        self._last_info_time_s = 0
    else:
        _LOGGER.error(f"Failed to power off device {self._deviceid}")
    
    return success
```

class AE200Climate(ClimateEntity):
def **init**(self, hass, device: AE200Device, controllerid: str, use_fahrenheit: bool = False):
self.*device = device
self.*use_fahrenheit = use_fahrenheit
self.entity_id = generate_entity_id(
“climate.{}”, f”autoh_mitsubishi_ae_200*{controllerid}*{device.getName()}”, None, hass
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
“AUTO”: “Auto”,
“LOW”: “Min (1/4)”,
“MID2”: “Low (2/4)”,
“MID1”: “High (3/4)”,
“HIGH”: “Max (4/4)”,
}
self._reverse_fan_mode_map = {v: k for k, v in self._fan_mode_map.items()}
self._attr_fan_modes = list(self._fan_mode_map.values())

```
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
    
    # Track when we set values to prevent immediate overwrite from device polling
    self._setting_temperature = False
    self._setting_mode = False
    self._setting_fan = False
    self._setting_swing = False
    self._last_temp_set_time = 0
    self._last_mode_set_time = 0
    self._last_fan_set_time = 0
    self._last_swing_set_time = 0
    self._ignore_updates_duration = 15  # Increased to 15 seconds for better reliability

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
    if self._current_temperature is None:
        return None
    return celsius_to_fahrenheit(self._current_temperature) if self._use_fahrenheit else self._current_temperature

@property
def target_temperature(self):
    if self._hvac_mode == HVACMode.HEAT_COOL:
        return None
    if self._target_temperature is None:
        return None
    return celsius_to_fahrenheit(self._target_temperature) if self._use_fahrenheit else self._target_temperature

@property
def target_temperature_high(self):
    if self._hvac_mode == HVACMode.HEAT_COOL:
        if self._target_temperature_high is None:
            return None
        return celsius_to_fahrenheit(self._target_temperature_high) if self._use_fahrenheit else self._target_temperature_high
    return None

@property
def target_temperature_low(self):
    if self._hvac_mode == HVACMode.HEAT_COOL:
        if self._target_temperature_low is None:
            return None
        return celsius_to_fahrenheit(self._target_temperature_low) if self._use_fahrenheit else self._target_temperature_low
    return None

@property
def min_temp(self):
    return MIN_TEMP_F if self._use_fahrenheit else MIN_TEMP_C

@property
def max_temp(self):
    return MAX_TEMP_F if self._use_fahrenheit else MAX_TEMP_C

@property
def fan_mode(self):
    if self._fan_mode in self._fan_mode_map:
        return self._fan_mode_map[self._fan_mode]
    return self._fan_mode

@property
def swing_mode(self):
    if self._swing_mode in self._swing_mode_map:
        return self._swing_mode_map[self._swing_mode]
    return self._swing_mode

@property
def hvac_mode(self):
    return self._hvac_mode

def _should_ignore_updates(self, update_type="temp"):
    """Check if we should ignore device updates for a specific type."""
    current_time = asyncio.get_event_loop().time()
    
    if update_type == "temp":
        return (current_time - self._last_temp_set_time) < self._ignore_updates_duration
    elif update_type == "mode":
        return (current_time - self._last_mode_set_time) < self._ignore_updates_duration
    elif update_type == "fan":
        return (current_time - self._last_fan_set_time) < self._ignore_updates_duration
    elif update_type == "swing":
        return (current_time - self._last_swing_set_time) < self._ignore_updates_duration
    
    return False

async def async_set_temperature(self, **kwargs):
    """Set target temperature with enhanced reliability."""
    _LOGGER.info(f"Setting temperature for {self.entity_id}: {kwargs}")
    current_time = asyncio.get_event_loop().time()
    
    temperature = kwargs.get(ATTR_TEMPERATURE)
    if temperature is not None:
        # Convert to Celsius for device communication
        temp_celsius = fahrenheit_to_celsius(temperature) if self._use_fahrenheit else temperature
        
        # Mark that we're setting temperature and track the time
        self._setting_temperature = True
        self._last_temp_set_time = current_time
        
        try:
            # Try to set the temperature on the device with verification
            success = await self._device.setTemperature(temp_celsius)
            
            if success:
                # Update our local state immediately for responsive UI
                self._target_temperature = temp_celsius
                self.async_write_ha_state()
                _LOGGER.info(f"Successfully set temperature to {temp_celsius}°C for {self.entity_id}")
            else:
                # If device didn't accept the change, reset ignore timer
                _LOGGER.error(f"Device rejected temperature change to {temp_celsius}°C for {self.entity_id}")
                self._last_temp_set_time = 0
                
        except Exception as exc:
            _LOGGER.error(f"Failed to set temperature for {self.entity_id}: {exc}")
            self._last_temp_set_time = 0
        finally:
            self._setting_temperature = False
        
    temp_low = kwargs.get("target_temp_low")
    temp_high = kwargs.get("target_temp_high")
    if temp_low is not None and temp_high is not None:
        # Convert to Celsius for device communication
        temp_low_celsius = fahrenheit_to_celsius(temp_low) if self._use_fahrenheit else temp_low
        temp_high_celsius = fahrenheit_to_celsius(temp_high) if self._use_fahrenheit else temp_high
        
        # Mark that we're setting temperature and track the time
        self._setting_temperature = True
        self._last_temp_set_time = current_time
        
        try:
            # Try to set both temperatures with verification
            high_success = await self._device.setTemperatureHigh(temp_high_celsius)
            low_success = await self._device.setTemperatureLow(temp_low_celsius)
            
            if high_success and low_success:
                # Update our local state immediately for responsive UI
                self._target_temperature_low = temp_low_celsius
                self._target_temperature_high = temp_high_celsius
                self.async_write_ha_state()
                _LOGGER.info(f"Successfully set temperature range {temp_low_celsius}-{temp_high_celsius}°C for {self.entity_id}")
            else:
                # If device didn't accept the changes, reset ignore timer
                _LOGGER.error(f"Device rejected temperature range change for {self.entity_id}")
                self._last_temp_set_time = 0
                
        except Exception as exc:
            _LOGGER.error(f"Failed to set temperature range for {self.entity_id}: {exc}")
            self._last_temp_set_time = 0
        finally:
            self._setting_temperature = False

async def async_set_hvac_mode(self, hvac_mode):
    """Set HVAC mode with enhanced reliability."""
    _LOGGER.info(f"Setting HVAC mode: {hvac_mode} for {self.entity_id}")
    current_time = asyncio.get_event_loop().time()
    self._setting_mode = True
    self._last_mode_set_time = current_time
    
    try:
        success = False
        if hvac_mode == HVACMode.OFF:
            success = await self._device.powerOff()
            if success:
                self._hvac_mode = HVACMode.OFF
        else:
            # First power on, then set mode
            power_success = await self._device.powerOn()
            if power_success:
                mode_map = {
                    HVACMode.HEAT: Mode.Heat,
                    HVACMode.COOL: Mode.Cool,
                    HVACMode.DRY: Mode.Dry,
                    HVACMode.FAN_ONLY: Mode.Fan,
                    HVACMode.HEAT_COOL: Mode.Auto,
                }
                mode_success = await self._device.setMode(mode_map.get(hvac_mode, Mode.Auto))
                if mode_success:
                    self._hvac_mode = hvac_mode
                    self._last_hvac_mode = hvac_mode
                    success = True
            
        if success:
            self.async_write_ha_state()
            _LOGGER.info(f"Successfully set HVAC mode to {hvac_mode} for {self.entity_id}")
        else:
            _LOGGER.error(f"Failed to set HVAC mode to {hvac_mode} for {self.entity_id}")
            self._last_mode_set_time = 0
            
    except Exception as exc:
        _LOGGER.error(f"Exception setting HVAC mode for {self.entity_id}: {exc}")
        self._last_mode_set_time = 0
    finally:
        self._setting_mode = False

async def async_set_fan_mode(self, fan_mode):
    """Set fan mode with enhanced reliability."""
    device_fan_mode = self._reverse_fan_mode_map.get(fan_mode, fan_mode)
    _LOGGER.info(f"Setting fan mode: {device_fan_mode} for {self.entity_id}")
    current_time = asyncio.get_event_loop().time()
    self._setting_fan = True
    self._last_fan_set_time = current_time
    
    try:
        success = await self._device.setFanSpeed(device_fan_mode)
        
        if success:
            self._fan_mode = device_fan_mode
            self.async_write_ha_state()
            _LOGGER.info(f"Successfully set fan mode to {device_fan_mode} for {self.entity_id}")
        else:
            _LOGGER.error(f"Failed to set fan mode for {self.entity_id}")
            self._last_fan_set_time = 0
            
    except Exception as exc:
        _LOGGER.error(f"Exception setting fan mode for {self.entity_id}: {exc}")
        self._last_fan_set_time = 0
    finally:
        self._setting_fan = False

async def async_set_swing_mode(self, swing_mode):
    """Set swing mode with enhanced reliability."""
    device_swing_mode = self._reverse_swing_mode_map.get(swing_mode, swing_mode)
    _LOGGER.info(f"Setting swing mode: {device_swing_mode} for {self.entity_id}")
    current_time = asyncio.get_event_loop().time()
    self._setting_swing = True
    self._last_swing_set_time = current_time
    
    try:
        success = await self._device.setSwingMode(device_swing_mode)
        
        if success:
            self._swing_mode = device_swing_mode
            self.async_write_ha_state()
            _LOGGER.info(f"Successfully set swing mode to {device_swing_mode} for {self.entity_id}")
        else:
            _LOGGER.error(f"Failed to set swing mode for {self.entity_id}")
            self._last_swing_set_time = 0
            
    except Exception as exc:
        _LOGGER.error(f"Exception setting swing mode for {self.entity_id}: {exc}")
        self._last_swing_set_time = 0
    finally:
        self._setting_swing = False

async def async_turn_on(self):
    """Turn on HVAC with enhanced reliability."""
    _LOGGER.info(f"Turning on HVAC mode: {self._last_hvac_mode} for {self.entity_id}")
    current_time = asyncio.get_event_loop().time()
    self._setting_mode = True
    self._last_mode_set_time = current_time
    
    try:
        success = await self._device.powerOn()
        
        if success:
            self._hvac_mode = self._last_hvac_mode
            self.async_write_ha_state()
            _LOGGER.info(f"Successfully turned on HVAC for {self.entity_id}")
        else:
            _LOGGER.error(f"Failed to turn on HVAC for {self.entity_id}")
            self._last_mode_set_time = 0
            
    except Exception as exc:
        _LOGGER.error(f"Exception turning on HVAC for {self.entity_id}: {exc}")
        self._last_mode_set_time = 0
    finally:
        self._setting_mode = False
    
async def async_turn_off(self):
    """Turn off HVAC with enhanced reliability."""
    _LOGGER.info(f"Turning off HVAC for {self.entity_id}")
    current_time = asyncio.get_event_loop().time()
    self._setting_mode = True
    self._last_mode_set_time = current_time
    
    try:
        success = await self._device.powerOff()
        
        if success:
            self._hvac_mode = HVACMode.OFF
            self.async_write_ha_state()
            _LOGGER.info(f"Successfully turned off HVAC for {self.entity_id}")
        else:
            _LOGGER.error(f"Failed to turn off HVAC for {self.entity_id}")
            self._last_mode_set_time = 0
            
    except Exception as exc:
        _LOGGER.error(f"Exception turning off HVAC for {self.entity_id}: {exc}")
        self._last_mode_set_time = 0
    finally:
        self._setting_mode = False

async def async_update(self):
    """Update entity state with smart polling management."""
    _LOGGER.debug(f"Updating climate entity: {self.entity_id}")
    
    # Skip update if we're currently setting values
    if (self._setting_temperature or self._setting_mode or 
        self._setting_fan or self._setting_swing):
        _LOGGER.debug(f"Skipping update for {self.entity_id} - currently setting values")
        return
        
    await self._device._refresh_device_info_async()
    
    # Always update current temperature (room temperature)
    self._current_temperature = await self._device.getRoomTemperature()
    
    # Update fan mode only if we haven't set it recently
    if not self._should_ignore_updates("fan"):
        self._fan_mode = await self._device.getFanSpeed()
    else:
        _LOGGER.debug(f"Ignoring fan mode update for {self.entity_id} - recently set")
        
    # Update swing mode only if we haven't set it recently  
    if not self._should_ignore_updates("swing"):
        self._swing_mode = await self._device.getSwingMode()
    else:
        _LOGGER.debug(f"Ignoring swing mode update for {self.entity_id} - recently set")
        
    if await self._device.isPowerOn():
        # Update target temperatures only if we haven't set them recently
        if not self._should_ignore_updates("temp"):
            self._target_temperature = await self._device.getTargetTemperature()
            self._target_temperature_high = await self._device.getTargetTemperatureHigh()
            self._target_temperature_low = await self._device.getTargetTemperatureLow()
        else:
            _LOGGER.debug(f"Ignoring temperature update for {self.entity_id} - recently set")
            
        # Update HVAC mode only if we haven't set it recently
        if not self._should_ignore_updates("mode"):
            mode = await self._device.getMode()
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
                if not self._should_ignore_updates("temp"):
                    self._target_temperature = None
            elif mode == Mode.Auto:
                self._hvac_mode = HVACMode.HEAT_COOL
                self._last_hvac_mode = HVACMode.HEAT_COOL
            else:
                self._hvac_mode = HVACMode.HEAT_COOL
                self._last_hvac_mode = HVACMode.HEAT_COOL
        else:
            _LOGGER.debug(f"Ignoring mode update for {self.entity_id} - recently set")
    else:
        # Device is off - only update if we haven't set mode recently
        if not self._should_ignore_updates("mode"):
            self._hvac_mode = HVACMode.OFF
        if not self._should_ignore_updates("temp"):
            self._target_temperature = None
            self._target_temperature_high = None
            self._target_temperature_low = None
```

async def async_setup_entry(
hass: HomeAssistant,
config_entry: ConfigEntry,
async_add_entities: AddEntitiesCallback,
) -> None:
“”“Set up AutoH Mitsubishi AE200 climate devices from config entry.”””
_LOGGER.info(“Setting up AutoH Mitsubishi AE200 platform…”)

```
config = hass.data[DOMAIN][config_entry.entry_id]
controllerid = config[CONF_CONTROLLER_ID]
ipaddress = config[CONF_IP_ADDRESS]
use_fahrenheit = config.get(CONF_TEMPERATURE_UNIT) == TEMP_FAHRENHEIT

mitsubishi_ae200_functions = MitsubishiAE200Functions()
devices = []

try:
    # Get device list from controller
    group_list = await mitsubishi_ae200_functions.getDevicesAsync(ipaddress)
    for group in group_list:
        device = AE200Device(ipaddress, group["id"], group["name"], mitsubishi_ae200_functions)
        devices.append(AE200Climate(hass, device, controllerid, use_fahrenheit))

    if devices:
        async_add_entities(devices, update_before_add=True)
        _LOGGER.info(f"Added {len(devices)} AutoH Mitsubishi AE200 device(s).")
    else:
        _LOGGER.warning("No AutoH Mitsubishi AE200 devices found.")
except Exception as exc:
    _LOGGER.error("Error setting up AutoH Mitsubishi AE200 devices: %s", exc)
```
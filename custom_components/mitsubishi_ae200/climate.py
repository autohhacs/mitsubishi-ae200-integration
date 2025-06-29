"""Climate platform for AutoH Mitsubishi AE200 integration - Debug Version."""
import logging
import asyncio

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import HVACMode, ClimateEntityFeature
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE

from .mitsubishi_ae200 import MitsubishiAE200Functions

_LOGGER = logging.getLogger(__name__)
DOMAIN = "mitsubishi_ae200"

MIN_TEMP_F = 61
MAX_TEMP_F = 86


def celsius_to_fahrenheit(celsius):
    """Convert Celsius to Fahrenheit with proper rounding."""
    if celsius is None:
        return None
    # Use more precise calculation and round to nearest integer
    fahrenheit = (celsius * 9.0/5.0) + 32.0
    return round(fahrenheit)


def fahrenheit_to_celsius(fahrenheit):
    """Convert Fahrenheit to Celsius with proper rounding."""
    if fahrenheit is None:
        return None
    # Use more precise calculation and round to nearest integer  
    celsius = (fahrenheit - 32.0) * 5.0/9.0
    return round(celsius)


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
        self._info_lease_seconds = 30

    async def _refresh_device_info_async(self):
        try:
            self._attributes = await self._mitsubishi_ae200_functions.getDeviceInfoAsync(
                self._ipaddress, self._deviceid, self._username, self._password
            )
            self._last_info_time_s = asyncio.get_event_loop().time()
            _LOGGER.info(f"DEBUG: Device {self._name} ALL attributes: {self._attributes}")
        except Exception as e:
            _LOGGER.error(f"Failed to refresh {self._name}: {e}")
            raise

    async def _get_info(self, key, default_value):
        current_time = asyncio.get_event_loop().time()
        if not self._attributes or (current_time - self._last_info_time_s) > self._info_lease_seconds:
            await self._refresh_device_info_async()
        value = self._attributes.get(key, default_value)
        _LOGGER.debug(f"DEBUG: Getting {key} = {value} for {self._name}")
        return value

    async def _to_float(self, value):
        try:
            result = float(value) if value is not None and str(value).strip() != "" else None
            _LOGGER.debug(f"DEBUG: Converting '{value}' to float: {result}")
            return result
        except (ValueError, TypeError) as e:
            _LOGGER.warning(f"DEBUG: Failed to convert '{value}' to float: {e}")
            return None

    def getName(self):
        return self._name

    async def getRoomTemperature(self):
        try:
            temp = await self._to_float(await self._get_info("InletTemp", None))
            _LOGGER.debug(f"DEBUG: Room temperature for {self._name}: {temp}°C")
            return temp
        except Exception as e:
            _LOGGER.error(f"Error getting room temp for {self._name}: {e}")
            return None

    async def getTargetTemperature(self):
        try:
            mode = await self.getMode()
            _LOGGER.info(f"DEBUG: Current mode is {mode} for {self._name}")
            
            # Check both temperature setpoints and log them
            settemp1 = await self._get_info("SetTemp1", None)
            settemp2 = await self._get_info("SetTemp2", None)
            settemp = await self._get_info("SetTemp", None)
            
            _LOGGER.info(f"DEBUG: Temperature values - SetTemp1: {settemp1}, SetTemp2: {settemp2}, SetTemp: {settemp}")
            
            if mode == "HEAT":
                temp = await self._to_float(settemp2)
                _LOGGER.info(f"DEBUG: Using SetTemp2 for HEAT mode: {temp}")
                return temp
            else:
                temp = await self._to_float(settemp1)
                _LOGGER.info(f"DEBUG: Using SetTemp1 for COOL/AUTO mode: {temp}")
                return temp
        except Exception as e:
            _LOGGER.error(f"Error getting target temp for {self._name}: {e}")
            return None

    async def getMode(self):
        try:
            mode = await self._get_info("Mode", "AUTO")
            _LOGGER.debug(f"DEBUG: Mode for {self._name}: {mode}")
            return mode
        except Exception as e:
            _LOGGER.error(f"Error getting mode for {self._name}: {e}")
            return "AUTO"

    async def isPowerOn(self):
        try:
            drive_status = await self._get_info("Drive", "OFF")
            is_on = drive_status == "ON"
            _LOGGER.debug(f"DEBUG: Power status for {self._name}: Drive={drive_status}, PowerOn={is_on}")
            return is_on
        except Exception as e:
            _LOGGER.error(f"Error getting power status for {self._name}: {e}")
            return False

    async def setTemperature(self, temperature):
        """Set temperature on the device. Temperature should be in Celsius."""
        try:
            _LOGGER.info(f"DEBUG: ===== SETTING TEMPERATURE =====")
            _LOGGER.info(f"DEBUG: Input temperature: {temperature}°C for {self._name}")
            
            # Get current state before setting
            current_mode = await self.getMode()
            current_power = await self.isPowerOn()
            current_target = await self.getTargetTemperature()
            
            _LOGGER.info(f"DEBUG: Current state - Mode: {current_mode}, Power: {current_power}, Target: {current_target}°C")
            
            # Round temperature properly
            temp_value = int(round(temperature))
            temp_str = str(temp_value)
            
            _LOGGER.info(f"DEBUG: Setting temperature to {temp_value}°C (rounded from {temperature})")
            
            # Clear cache to get fresh data after command
            self._last_info_time_s = 0
            
            # Try multiple strategies to set temperature
            _LOGGER.info(f"DEBUG: Strategy 1 - Mode-specific temperature setting")
            
            if current_mode == "HEAT":
                _LOGGER.info(f"DEBUG: Sending SetTemp2={temp_str} for HEAT mode")
                await self._mitsubishi_ae200_functions.sendAsync(
                    self._ipaddress, self._deviceid, {"SetTemp2": temp_str}, 
                    self._username, self._password
                )
            else:
                _LOGGER.info(f"DEBUG: Sending SetTemp1={temp_str} for {current_mode} mode")
                await self._mitsubishi_ae200_functions.sendAsync(
                    self._ipaddress, self._deviceid, {"SetTemp1": temp_str}, 
                    self._username, self._password
                )
            
            # Wait for device to process
            await asyncio.sleep(2)
            
            # Strategy 2: Try the generic SetTemp parameter
            _LOGGER.info(f"DEBUG: Strategy 2 - Generic SetTemp parameter")
            try:
                await self._mitsubishi_ae200_functions.sendAsync(
                    self._ipaddress, self._deviceid, {"SetTemp": temp_str}, 
                    self._username, self._password
                )
                _LOGGER.info(f"DEBUG: Sent SetTemp={temp_str}")
            except Exception as e:
                _LOGGER.warning(f"DEBUG: SetTemp failed (may be normal): {e}")
            
            await asyncio.sleep(2)
            
            # Strategy 3: Try setting both SetTemp1 and SetTemp2
            _LOGGER.info(f"DEBUG: Strategy 3 - Setting both temperature parameters")
            try:
                await self._mitsubishi_ae200_functions.sendAsync(
                    self._ipaddress, self._deviceid, {
                        "SetTemp1": temp_str,
                        "SetTemp2": temp_str
                    }, 
                    self._username, self._password
                )
                _LOGGER.info(f"DEBUG: Sent both SetTemp1={temp_str} and SetTemp2={temp_str}")
            except Exception as e:
                _LOGGER.warning(f"DEBUG: Dual temperature setting failed: {e}")
            
            await asyncio.sleep(2)
            
            # Verify the change took effect
            _LOGGER.info(f"DEBUG: Verifying temperature change...")
            self._last_info_time_s = 0  # Force refresh
            new_target = await self.getTargetTemperature()
            new_mode = await self.getMode()
            
            _LOGGER.info(f"DEBUG: After setting - Mode: {new_mode}, New Target: {new_target}°C")
            
            if new_target == temp_value:
                _LOGGER.info(f"DEBUG: ✅ Temperature successfully set to {temp_value}°C")
            else:
                _LOGGER.warning(f"DEBUG: ❌ Temperature setting may have failed. Expected: {temp_value}°C, Got: {new_target}°C")
            
            _LOGGER.info(f"DEBUG: ===== TEMPERATURE SETTING COMPLETE =====")
            
        except Exception as e:
            _LOGGER.error(f"Failed to set temperature for {self._name}: {e}")
            raise

    async def setMode(self, mode):
        try:
            _LOGGER.info(f"DEBUG: Setting mode to {mode} for {self._name}")
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Mode": mode}, 
                self._username, self._password
            )
            self._last_info_time_s = 0
            await asyncio.sleep(2)
            
            # Verify mode change
            new_mode = await self.getMode()
            _LOGGER.info(f"DEBUG: Mode changed from ? to {new_mode}")
        except Exception as e:
            _LOGGER.error(f"Failed to set mode for {self._name}: {e}")
            raise

    async def powerOn(self):
        try:
            _LOGGER.info(f"DEBUG: Powering on {self._name}")
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Drive": "ON"}, 
                self._username, self._password
            )
            self._last_info_time_s = 0
            await asyncio.sleep(2)
            
            # Verify power change
            is_on = await self.isPowerOn()
            _LOGGER.info(f"DEBUG: Power status after ON command: {is_on}")
        except Exception as e:
            _LOGGER.error(f"Failed to power on {self._name}: {e}")
            raise

    async def powerOff(self):
        try:
            _LOGGER.info(f"DEBUG: Powering off {self._name}")
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Drive": "OFF"}, 
                self._username, self._password
            )
            self._last_info_time_s = 0
            await asyncio.sleep(2)
            
            # Verify power change
            is_on = await self.isPowerOn()
            _LOGGER.info(f"DEBUG: Power status after OFF command: {is_on}")
        except Exception as e:
            _LOGGER.error(f"Failed to power off {self._name}: {e}")
            raise


class AE200Climate(ClimateEntity):
    def __init__(self, hass, device: AE200Device, controllerid: str, ipaddress: str):
        self._device = device
        ip_suffix = ipaddress.replace(".", "_").replace(":", "_")
        self._attr_unique_id = f"mitsubishi_ae200_{controllerid}_{ip_suffix}_{device._deviceid}"
        self._attr_name = f"AutoH {device.getName()}"
        
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
        
        self._current_temperature = None
        self._target_temperature = None
        self._hvac_mode = HVACMode.OFF
        self._last_hvac_mode = HVACMode.COOL

    @property
    def unique_id(self):
        return self._attr_unique_id

    @property
    def name(self):
        return self._attr_name

    @property
    def temperature_unit(self):
        return self._attr_temperature_unit

    @property
    def current_temperature(self):
        if self._current_temperature is None:
            return None
        fahrenheit = celsius_to_fahrenheit(self._current_temperature)
        _LOGGER.debug(f"DEBUG: Converting current temp {self._current_temperature}°C to {fahrenheit}°F")
        return fahrenheit

    @property
    def target_temperature(self):
        if self._target_temperature is None:
            return None
        fahrenheit = celsius_to_fahrenheit(self._target_temperature)
        _LOGGER.debug(f"DEBUG: Converting target temp {self._target_temperature}°C to {fahrenheit}°F")
        return fahrenheit

    @property
    def min_temp(self):
        return MIN_TEMP_F

    @property
    def max_temp(self):
        return MAX_TEMP_F

    @property
    def hvac_mode(self):
        return self._hvac_mode

    @property
    def hvac_modes(self):
        return self._attr_hvac_modes

    @property
    def supported_features(self):
        return self._attr_supported_features

    @property
    def should_poll(self):
        return True

    async def async_turn_on(self):
        try:
            _LOGGER.info(f"DEBUG: Turning on {self.name}")
            await self._device.powerOn()
            self._hvac_mode = self._last_hvac_mode
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to turn on {self.name}: {e}")
            raise

    async def async_turn_off(self):
        try:
            _LOGGER.info(f"DEBUG: Turning off {self.name}")
            await self._device.powerOff()
            self._hvac_mode = HVACMode.OFF
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"Failed to turn off {self.name}: {e}")
            raise

    async def async_set_temperature(self, **kwargs):
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            try:
                _LOGGER.info(f"DEBUG: ===== HOME ASSISTANT TEMPERATURE CHANGE =====")
                _LOGGER.info(f"DEBUG: Home Assistant requesting temperature change to {temperature}°F for {self.name}")
                
                temp_celsius = fahrenheit_to_celsius(temperature)
                _LOGGER.info(f"DEBUG: Converted {temperature}°F to {temp_celsius}°C")
                
                # Make sure device is powered on before setting temperature
                is_powered = await self._device.isPowerOn()
                if not is_powered:
                    _LOGGER.info(f"DEBUG: Device is off, turning on first...")
                    await self._device.powerOn()
                    await asyncio.sleep(2)
                
                await self._device.setTemperature(temp_celsius)
                self._target_temperature = temp_celsius
                self.async_write_ha_state()
                
                _LOGGER.info(f"DEBUG: Home Assistant temperature change completed")
                _LOGGER.info(f"DEBUG: ===== HOME ASSISTANT TEMPERATURE CHANGE COMPLETE =====")
            except Exception as e:
                _LOGGER.error(f"Failed to set temperature for {self.name}: {e}")
                raise

    async def async_set_hvac_mode(self, hvac_mode):
        try:
            _LOGGER.info(f"DEBUG: Setting HVAC mode to {hvac_mode} for {self.name}")
            
            if hvac_mode == HVACMode.OFF:
                await self._device.powerOff()
                self._hvac_mode = HVACMode.OFF
            else:
                await self._device.powerOn()
                mode_map = {
                    HVACMode.HEAT: "HEAT",
                    HVACMode.COOL: "COOL", 
                    HVACMode.AUTO: "AUTO",
                }
                device_mode = mode_map.get(hvac_mode, "AUTO")
                await self._device.setMode(device_mode)
                self._hvac_mode = hvac_mode
                self._last_hvac_mode = hvac_mode
                
            self.async_write_ha_state()
            _LOGGER.info(f"DEBUG: HVAC mode change completed: {hvac_mode}")
        except Exception as e:
            _LOGGER.error(f"Failed to set HVAC mode for {self.name}: {e}")
            raise

    async def async_update(self):
        try:
            _LOGGER.debug(f"DEBUG: Updating {self.name}...")
            
            self._current_temperature = await self._device.getRoomTemperature()
            
            if await self._device.isPowerOn():
                self._target_temperature = await self._device.getTargetTemperature()
                mode = await self._device.getMode()
                
                if mode == "HEAT":
                    self._hvac_mode = HVACMode.HEAT
                    self._last_hvac_mode = HVACMode.HEAT
                elif mode == "COOL":
                    self._hvac_mode = HVACMode.COOL
                    self._last_hvac_mode = HVACMode.COOL
                else:
                    self._hvac_mode = HVACMode.AUTO
                    self._last_hvac_mode = HVACMode.AUTO
            else:
                self._target_temperature = None
                self._hvac_mode = HVACMode.OFF
                
            _LOGGER.debug(f"DEBUG: Update completed - Current: {self._current_temperature}°C, Target: {self._target_temperature}°C, Mode: {self._hvac_mode}")
                
        except Exception as e:
            _LOGGER.error(f"Failed to update {self.name}: {e}")


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up climate devices."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    controllerid = config["controller_id"]
    ipaddress = config["ip_address"]
    username = config["username"]
    password = config["password"]

    mitsubishi_ae200_functions = MitsubishiAE200Functions()
    devices = []
    
    try:
        group_list = await mitsubishi_ae200_functions.getDevicesAsync(ipaddress, username, password)
        
        for group in group_list:
            device_id = group["id"]
            device_name = group["name"]
            
            device = AE200Device(ipaddress, device_id, device_name, mitsubishi_ae200_functions, username, password)
            climate_entity = AE200Climate(hass, device, controllerid, ipaddress)
            devices.append(climate_entity)

        if devices:
            async_add_entities(devices, update_before_add=True)
            _LOGGER.info(f"Added {len(devices)} climate entities")
        else:
            _LOGGER.warning("No devices found")
            
    except Exception as exc:
        _LOGGER.error(f"Setup error: {exc}", exc_info=True)
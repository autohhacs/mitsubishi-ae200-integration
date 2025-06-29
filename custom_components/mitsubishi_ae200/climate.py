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
MIN_TEMP_F = 61
MAX_TEMP_F = 86


def celsius_to_fahrenheit_exact(celsius):
    """Convert Celsius to Fahrenheit with exact precision."""
    if celsius is None:
        return None
    return (celsius * 9.0/5.0) + 32.0


def fahrenheit_to_celsius_exact(fahrenheit):
    """Convert Fahrenheit to Celsius with exact precision."""
    if fahrenheit is None:
        return None
    return (fahrenheit - 32.0) * 5.0/9.0


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
        self._info_lease_seconds = 10

    async def _refresh_device_info_async(self):
        """Refresh device information from the controller."""
        _LOGGER.info(f"🔄 Refreshing device info for {self._name} (ID: {self._deviceid})")
        try:
            self._attributes = await self._mitsubishi_ae200_functions.getDeviceInfoAsync(
                self._ipaddress, self._deviceid, self._username, self._password
            )
            self._last_info_time_s = asyncio.get_event_loop().time()
            
            # Log ALL attributes to understand what the device is sending
            _LOGGER.info(f"📊 {self._name} - ALL DEVICE ATTRIBUTES:")
            for key, value in self._attributes.items():
                _LOGGER.info(f"   {key}: {value}")
                
        except Exception as e:
            _LOGGER.error(f"❌ Failed to refresh device info for {self._deviceid}: {e}")
            raise

    async def _get_info(self, key, default_value):
        """Get device information, refreshing if needed."""
        current_time = asyncio.get_event_loop().time()
        if not self._attributes or (current_time - self._last_info_time_s) > self._info_lease_seconds:
            await self._refresh_device_info_async()
        value = self._attributes.get(key, default_value)
        _LOGGER.debug(f"🔍 {self._name} - {key}: '{value}' (type: {type(value)})")
        return value

    async def _to_float(self, value):
        """Convert value to float safely."""
        try:
            if value is None or str(value).strip() == "":
                _LOGGER.debug(f"⚠️ Empty value: '{value}'")
                return None
            result = float(value)
            _LOGGER.debug(f"✅ Converted '{value}' to float: {result}")
            return result
        except (ValueError, TypeError) as e:
            _LOGGER.warning(f"❌ Could not convert '{value}' to float: {e}")
            return None

    def getName(self):
        """Get device name."""
        return self._name

    async def getRoomTemperature(self):
        """Get current room temperature - RAW VALUE."""
        try:
            # Get the raw temperature value
            raw_temp = await self._get_info("InletTemp", None)
            temp_float = await self._to_float(raw_temp)
            
            _LOGGER.info(f"🌡️ {self._name} - RAW InletTemp: '{raw_temp}' -> {temp_float}")
            
            # Check if we need to look at other temperature fields
            other_temps = {}
            for key in self._attributes:
                if 'temp' in key.lower():
                    other_temps[key] = self._attributes[key]
            
            if other_temps:
                _LOGGER.info(f"🌡️ {self._name} - All temperature fields: {other_temps}")
            
            return temp_float
        except Exception as e:
            _LOGGER.error(f"❌ Error getting room temperature for {self._name}: {e}")
            return None

    async def getTargetTemperature(self):
        """Get target temperature based on current mode."""
        try:
            mode = await self.getMode()
            _LOGGER.info(f"🎯 {self._name} - Getting target temp for mode: {mode}")
            
            if mode == Mode.Heat:
                raw_temp = await self._get_info("SetTemp2", None)
                temp = await self._to_float(raw_temp)
                _LOGGER.info(f"🔥 {self._name} - Heating target (SetTemp2): '{raw_temp}' -> {temp}")
                return temp
            else:
                raw_temp = await self._get_info("SetTemp1", None)
                temp = await self._to_float(raw_temp)
                _LOGGER.info(f"❄️ {self._name} - Cooling target (SetTemp1): '{raw_temp}' -> {temp}")
                return temp
        except Exception as e:
            _LOGGER.error(f"❌ Error getting target temperature for {self._name}: {e}")
            return None

    async def getMode(self):
        """Get current operating mode."""
        try:
            mode = await self._get_info("Mode", Mode.Auto)
            _LOGGER.info(f"🔧 {self._name} - Current mode: {mode}")
            return mode
        except Exception as e:
            _LOGGER.error(f"❌ Error getting mode for {self._name}: {e}")
            return Mode.Auto

    async def isPowerOn(self):
        """Check if device is powered on."""
        try:
            drive_status = await self._get_info("Drive", "OFF")
            is_on = drive_status == "ON"
            _LOGGER.info(f"⚡ {self._name} - Drive status: '{drive_status}' -> Power On: {is_on}")
            return is_on
        except Exception as e:
            _LOGGER.error(f"❌ Error getting power status for {self._name}: {e}")
            return False

    async def setTemperature(self, temperature):
        """Set target temperature based on current mode."""
        try:
            mode = await self.getMode()
            temp_int = int(round(temperature))
            temp_str = str(temp_int)
            
            _LOGGER.info(f"🌡️ SETTING TEMPERATURE for {self._name}:")
            _LOGGER.info(f"   Input: {temperature} -> Rounded: {temp_int} -> String: '{temp_str}'")
            _LOGGER.info(f"   Current mode: {mode}")
            
            # Determine which field to set based on mode
            if mode == Mode.Heat:
                field = "SetTemp2"
                _LOGGER.info(f"🔥 Setting HEATING temperature: {field}={temp_str}")
            else:
                field = "SetTemp1"
                _LOGGER.info(f"❄️ Setting COOLING temperature: {field}={temp_str}")
            
            # Send the command
            command = {field: temp_str}
            _LOGGER.info(f"📤 Sending command to {self._name}: {command}")
            
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, command, 
                self._username, self._password
            )
            
            _LOGGER.info(f"✅ Command sent successfully to {self._name}")
            
            # Force refresh to see if it worked
            self._last_info_time_s = 0
            await asyncio.sleep(3)  # Wait longer for device to respond
            await self._refresh_device_info_async()
            
            # Verify the change
            new_target = await self.getTargetTemperature()
            _LOGGER.info(f"🔍 Verification - New target temperature: {new_target}")
            
        except Exception as e:
            _LOGGER.error(f"❌ Failed to set temperature for {self._name}: {e}")
            raise

    async def setMode(self, mode):
        """Set operating mode."""
        try:
            _LOGGER.info(f"🔧 Setting mode for {self._name}: {mode}")
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Mode": mode}, 
                self._username, self._password
            )
            _LOGGER.info(f"✅ Mode set successfully for {self._name}")
            self._last_info_time_s = 0
        except Exception as e:
            _LOGGER.error(f"❌ Failed to set mode for {self._name}: {e}")
            raise

    async def powerOn(self):
        """Turn on the device."""
        try:
            _LOGGER.info(f"⚡ Powering ON {self._name}")
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Drive": "ON"}, 
                self._username, self._password
            )
            _LOGGER.info(f"✅ Power ON successful for {self._name}")
            self._last_info_time_s = 0
        except Exception as e:
            _LOGGER.error(f"❌ Failed to power on {self._name}: {e}")
            raise

    async def powerOff(self):
        """Turn off the device."""
        try:
            _LOGGER.info(f"⚡ Powering OFF {self._name}")
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Drive": "OFF"}, 
                self._username, self._password
            )
            _LOGGER.info(f"✅ Power OFF successful for {self._name}")
            self._last_info_time_s = 0
        except Exception as e:
            _LOGGER.error(f"❌ Failed to power off {self._name}: {e}")
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
        
        _LOGGER.info(f"🏠 Created climate entity: {self._attr_name} (Fahrenheit: {use_fahrenheit})")

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
        """Return the current temperature with proper conversion."""
        if self._current_temperature is None:
            return None
            
        # The device sends temperature in its native format
        # We need to figure out if it's Celsius or Fahrenheit
        raw_temp = self._current_temperature
        
        if self._use_fahrenheit:
            # If we're displaying in Fahrenheit
            if raw_temp > 50:
                # Raw value is likely already in Fahrenheit
                result = round(raw_temp)
                _LOGGER.debug(f"🌡️ {self.name} - Current temp (F->F): {raw_temp} -> {result}")
            else:
                # Raw value is in Celsius, convert to Fahrenheit
                result = round(celsius_to_fahrenheit_exact(raw_temp))
                _LOGGER.debug(f"🌡️ {self.name} - Current temp (C->F): {raw_temp} -> {result}")
        else:
            # If we're displaying in Celsius
            if raw_temp > 50:
                # Raw value is in Fahrenheit, convert to Celsius
                result = round(fahrenheit_to_celsius_exact(raw_temp))
                _LOGGER.debug(f"🌡️ {self.name} - Current temp (F->C): {raw_temp} -> {result}")
            else:
                # Raw value is already in Celsius
                result = round(raw_temp)
                _LOGGER.debug(f"🌡️ {self.name} - Current temp (C->C): {raw_temp} -> {result}")
        
        return result

    @property
    def target_temperature(self):
        """Return the target temperature with proper conversion."""
        if self._target_temperature is None:
            return None
            
        raw_temp = self._target_temperature
        
        if self._use_fahrenheit:
            if raw_temp > 50:
                result = round(raw_temp)
                _LOGGER.debug(f"🎯 {self.name} - Target temp (F->F): {raw_temp} -> {result}")
            else:
                result = round(celsius_to_fahrenheit_exact(raw_temp))
                _LOGGER.debug(f"🎯 {self.name} - Target temp (C->F): {raw_temp} -> {result}")
        else:
            if raw_temp > 50:
                result = round(fahrenheit_to_celsius_exact(raw_temp))
                _LOGGER.debug(f"🎯 {self.name} - Target temp (F->C): {raw_temp} -> {result}")
            else:
                result = round(raw_temp)
                _LOGGER.debug(f"🎯 {self.name} - Target temp (C->C): {raw_temp} -> {result}")
        
        return result

    @property
    def min_temp(self):
        return MIN_TEMP_F if self._use_fahrenheit else MIN_TEMP_C

    @property
    def max_temp(self):
        return MAX_TEMP_F if self._use_fahrenheit else MAX_TEMP_C

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

    async def async_set_temperature(self, **kwargs):
        """Set temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            _LOGGER.info(f"🌡️ HOME ASSISTANT REQUESTING TEMPERATURE CHANGE:")
            _LOGGER.info(f"   Entity: {self.name}")
            _LOGGER.info(f"   Requested: {temperature}°{self.temperature_unit}")
            _LOGGER.info(f"   Current target: {self.target_temperature}°{self.temperature_unit}")
            
            try:
                # Convert the temperature to what the device expects
                if self._use_fahrenheit:
                    # HA is sending Fahrenheit, but device might expect Celsius
                    # First, let's see what format the device expects by checking current values
                    await self._device._refresh_device_info_async()
                    
                    # If target temp is > 50, device probably uses Fahrenheit
                    # If target temp is < 50, device probably uses Celsius
                    current_target_raw = self._target_temperature
                    
                    if current_target_raw and current_target_raw > 50:
                        # Device uses Fahrenheit
                        device_temp = temperature
                        _LOGGER.info(f"   Device expects Fahrenheit: {device_temp}°F")
                    else:
                        # Device uses Celsius
                        device_temp = fahrenheit_to_celsius_exact(temperature)
                        _LOGGER.info(f"   Device expects Celsius: {device_temp}°C (converted from {temperature}°F)")
                else:
                    # HA is sending Celsius
                    if self._target_temperature and self._target_temperature > 50:
                        # Device uses Fahrenheit
                        device_temp = celsius_to_fahrenheit_exact(temperature)
                        _LOGGER.info(f"   Device expects Fahrenheit: {device_temp}°F (converted from {temperature}°C)")
                    else:
                        # Device uses Celsius
                        device_temp = temperature
                        _LOGGER.info(f"   Device expects Celsius: {device_temp}°C")
                
                await self._device.setTemperature(device_temp)
                
                # Update our internal state
                self._target_temperature = device_temp
                self.async_write_ha_state()
                
            except Exception as e:
                _LOGGER.error(f"❌ Failed to set temperature for {self.name}: {e}")

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode."""
        _LOGGER.info(f"🔧 Setting HVAC mode: {hvac_mode} for {self.name}")
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
            _LOGGER.error(f"❌ Failed to set HVAC mode for {self.name}: {e}")

    async def async_update(self):
        """Update the entity state."""
        _LOGGER.debug(f"🔄 Updating {self.name}")
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
                
            _LOGGER.debug(f"✅ {self.name} updated: current={self.current_temperature}°{self.temperature_unit}, target={self.target_temperature}°{self.temperature_unit}, mode={self._hvac_mode}")
            
        except Exception as e:
            _LOGGER.error(f"❌ Failed to update {self.name}: {e}")

    async def async_turn_on(self):
        """Turn on the HVAC."""
        try:
            await self._device.powerOn()
            self._hvac_mode = self._last_hvac_mode
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"❌ Failed to turn on {self.name}: {e}")

    async def async_turn_off(self):
        """Turn off the HVAC."""
        try:
            await self._device.powerOff()
            self._hvac_mode = HVACMode.OFF
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"❌ Failed to turn off {self.name}: {e}")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AutoH Mitsubishi AE200 climate devices from config entry."""
    _LOGGER.info("🚀 Setting up AutoH Mitsubishi AE200 platform...")

    config = hass.data[DOMAIN][config_entry.entry_id]
    controllerid = config[CONF_CONTROLLER_ID]
    ipaddress = config[CONF_IP_ADDRESS]
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]
    use_fahrenheit = config.get(CONF_TEMPERATURE_UNIT) == TEMP_FAHRENHEIT
    device_names = config.get("device_names", {})

    _LOGGER.info(f"📋 Config: Controller={controllerid}, IP={ipaddress}, Fahrenheit={use_fahrenheit}")

    mitsubishi_ae200_functions = MitsubishiAE200Functions()
    devices = []
    
    try:
        group_list = await mitsubishi_ae200_functions.getDevicesAsync(ipaddress, username, password)
        _LOGGER.info(f"🔍 Found {len(group_list)} devices: {group_list}")
        
        for group in group_list:
            device_id = group["id"]
            device_name = device_names.get(device_id, group["name"])
            
            _LOGGER.info(f"🏠 Creating device: ID={device_id}, Name={device_name}")
            
            device = AE200Device(ipaddress, device_id, device_name, mitsubishi_ae200_functions, username, password)
            climate_entity = AE200Climate(hass, device, controllerid, ipaddress, use_fahrenheit)
            devices.append(climate_entity)

        if devices:
            async_add_entities(devices, update_before_add=True)
            _LOGGER.info(f"✅ Successfully added {len(devices)} devices")
        else:
            _LOGGER.warning("⚠️ No devices found")
            
    except Exception as exc:
        _LOGGER.error(f"❌ Error setting up devices: {exc}", exc_info=True)

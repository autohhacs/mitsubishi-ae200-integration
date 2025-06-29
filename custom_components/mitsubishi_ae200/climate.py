"""Simple working climate platform - back to basics."""
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

class AE200Climate(ClimateEntity):
    def __init__(self, hass, ipaddress: str, deviceid: str, name: str, 
                 mitsubishi_ae200_functions: MitsubishiAE200Functions, 
                 username: str, password: str, controllerid: str):
        # Basic setup
        self._ipaddress = ipaddress
        self._deviceid = deviceid
        self._device_name = name
        self._functions = mitsubishi_ae200_functions
        self._username = username
        self._password = password
        
        # Entity properties
        ip_suffix = ipaddress.replace(".", "_")
        self._attr_unique_id = f"mitsubishi_ae200_{controllerid}_{ip_suffix}_{deviceid}"
        self._attr_name = f"AutoH {name}"
        
        # Climate properties
        self._attr_temperature_unit = UnitOfTemperature.FAHRENHEIT
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL, HVACMode.AUTO]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_ON | ClimateEntityFeature.TURN_OFF
        
        # State variables
        self._current_temperature = None
        self._target_temperature = None
        self._hvac_mode = HVACMode.OFF
        self._is_on = False
        self._device_data = {}
        
        _LOGGER.info(f"Created simple climate entity: {self._attr_name}")

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
        return self._current_temperature

    @property
    def target_temperature(self):
        return self._target_temperature

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

    @property
    def min_temp(self):
        return 60

    @property
    def max_temp(self):
        return 85

    async def _get_device_data(self):
        """Get raw data from device."""
        try:
            _LOGGER.info(f"Getting device data for {self._device_name}")
            self._device_data = await self._functions.getDeviceInfoAsync(
                self._ipaddress, self._deviceid, self._username, self._password
            )
            _LOGGER.info(f"Device {self._device_name} raw data: {self._device_data}")
            return True
        except Exception as e:
            _LOGGER.error(f"Failed to get device data for {self._device_name}: {e}")
            return False

    async def async_update(self):
        """Update the entity."""
        _LOGGER.info(f"Updating {self._device_name}")
        
        if not await self._get_device_data():
            return
            
        try:
            # Get power status
            drive = self._device_data.get("Drive", "OFF")
            self._is_on = (drive == "ON")
            _LOGGER.info(f"{self._device_name} - Drive: {drive}, Is On: {self._is_on}")
            
            # Get temperatures - try both Celsius and Fahrenheit interpretation
            inlet_temp_raw = self._device_data.get("InletTemp")
            settemp1_raw = self._device_data.get("SetTemp1")
            settemp2_raw = self._device_data.get("SetTemp2")
            mode_raw = self._device_data.get("Mode", "AUTO")
            
            _LOGGER.info(f"{self._device_name} - Raw temps: Inlet={inlet_temp_raw}, SetTemp1={settemp1_raw}, SetTemp2={settemp2_raw}, Mode={mode_raw}")
            
            # Convert temperatures
            if inlet_temp_raw:
                inlet_temp = float(inlet_temp_raw)
                # If value is < 50, assume it's Celsius and convert to Fahrenheit
                if inlet_temp < 50:
                    self._current_temperature = round((inlet_temp * 9/5) + 32)
                    _LOGGER.info(f"{self._device_name} - Converted current temp: {inlet_temp}°C -> {self._current_temperature}°F")
                else:
                    self._current_temperature = round(inlet_temp)
                    _LOGGER.info(f"{self._device_name} - Current temp (already F): {self._current_temperature}°F")
            
            # Set target temperature based on mode
            if self._is_on:
                if mode_raw == "HEAT" and settemp2_raw:
                    target_raw = float(settemp2_raw)
                elif settemp1_raw:
                    target_raw = float(settemp1_raw)
                else:
                    target_raw = None
                    
                if target_raw:
                    # If value is < 50, assume it's Celsius and convert to Fahrenheit
                    if target_raw < 50:
                        self._target_temperature = round((target_raw * 9/5) + 32)
                        _LOGGER.info(f"{self._device_name} - Converted target temp: {target_raw}°C -> {self._target_temperature}°F")
                    else:
                        self._target_temperature = round(target_raw)
                        _LOGGER.info(f"{self._device_name} - Target temp (already F): {self._target_temperature}°F")
            else:
                self._target_temperature = None
            
            # Set HVAC mode
            if not self._is_on:
                self._hvac_mode = HVACMode.OFF
            elif mode_raw == "HEAT":
                self._hvac_mode = HVACMode.HEAT
            elif mode_raw == "COOL":
                self._hvac_mode = HVACMode.COOL
            else:
                self._hvac_mode = HVACMode.AUTO
                
            _LOGGER.info(f"{self._device_name} - Final state: Current={self._current_temperature}°F, Target={self._target_temperature}°F, Mode={self._hvac_mode}")
            
        except Exception as e:
            _LOGGER.error(f"Error updating {self._device_name}: {e}")

    async def async_set_temperature(self, **kwargs):
        """Set target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
            
        _LOGGER.info(f"Setting {self._device_name} temperature to {temperature}°F")
        
        try:
            # Get current mode to determine which temperature field to set
            if not await self._get_device_data():
                return
                
            mode = self._device_data.get("Mode", "COOL")
            
            # Convert Fahrenheit to what the device expects
            # Try both Celsius and Fahrenheit
            temp_celsius = round((temperature - 32) * 5/9)
            temp_fahrenheit = round(temperature)
            
            _LOGGER.info(f"{self._device_name} - Trying to set: {temperature}°F as Celsius={temp_celsius} or Fahrenheit={temp_fahrenheit}")
            
            # Try Celsius first (most likely)
            try:
                if mode == "HEAT":
                    command = {"SetTemp2": str(temp_celsius)}
                else:
                    command = {"SetTemp1": str(temp_celsius)}
                    
                _LOGGER.info(f"{self._device_name} - Sending Celsius command: {command}")
                await self._functions.sendAsync(self._ipaddress, self._deviceid, command, self._username, self._password)
                
                # Wait and check if it worked
                await asyncio.sleep(3)
                if await self._get_device_data():
                    new_temp_raw = self._device_data.get("SetTemp1" if mode != "HEAT" else "SetTemp2")
                    if new_temp_raw and abs(float(new_temp_raw) - temp_celsius) <= 1:
                        _LOGGER.info(f"{self._device_name} - Celsius command worked! Device now shows {new_temp_raw}")
                        self._target_temperature = temperature
                        return
                        
            except Exception as e:
                _LOGGER.warning(f"{self._device_name} - Celsius command failed: {e}")
            
            # If Celsius didn't work, try Fahrenheit
            try:
                if mode == "HEAT":
                    command = {"SetTemp2": str(temp_fahrenheit)}
                else:
                    command = {"SetTemp1": str(temp_fahrenheit)}
                    
                _LOGGER.info(f"{self._device_name} - Sending Fahrenheit command: {command}")
                await self._functions.sendAsync(self._ipaddress, self._deviceid, command, self._username, self._password)
                
                # Wait and check if it worked
                await asyncio.sleep(3)
                if await self._get_device_data():
                    new_temp_raw = self._device_data.get("SetTemp1" if mode != "HEAT" else "SetTemp2")
                    if new_temp_raw and abs(float(new_temp_raw) - temp_fahrenheit) <= 1:
                        _LOGGER.info(f"{self._device_name} - Fahrenheit command worked! Device now shows {new_temp_raw}")
                        self._target_temperature = temperature
                        return
                        
            except Exception as e:
                _LOGGER.warning(f"{self._device_name} - Fahrenheit command failed: {e}")
                
            _LOGGER.error(f"{self._device_name} - Both temperature setting attempts failed")
            
        except Exception as e:
            _LOGGER.error(f"Error setting temperature for {self._device_name}: {e}")

    async def async_set_hvac_mode(self, hvac_mode):
        """Set HVAC mode."""
        _LOGGER.info(f"Setting {self._device_name} HVAC mode to {hvac_mode}")
        
        try:
            if hvac_mode == HVACMode.OFF:
                await self._functions.sendAsync(self._ipaddress, self._deviceid, {"Drive": "OFF"}, self._username, self._password)
                self._hvac_mode = HVACMode.OFF
                self._is_on = False
            else:
                # Turn on first
                await self._functions.sendAsync(self._ipaddress, self._deviceid, {"Drive": "ON"}, self._username, self._password)
                
                # Set mode
                if hvac_mode == HVACMode.HEAT:
                    await self._functions.sendAsync(self._ipaddress, self._deviceid, {"Mode": "HEAT"}, self._username, self._password)
                elif hvac_mode == HVACMode.COOL:
                    await self._functions.sendAsync(self._ipaddress, self._deviceid, {"Mode": "COOL"}, self._username, self._password)
                else:
                    await self._functions.sendAsync(self._ipaddress, self._deviceid, {"Mode": "AUTO"}, self._username, self._password)
                
                self._hvac_mode = hvac_mode
                self._is_on = True
                
            self.async_write_ha_state()
            
        except Exception as e:
            _LOGGER.error(f"Error setting HVAC mode for {self._device_name}: {e}")

    async def async_turn_on(self):
        """Turn the entity on."""
        await self.async_set_hvac_mode(HVACMode.AUTO)

    async def async_turn_off(self):
        """Turn the entity off."""
        await self.async_set_hvac_mode(HVACMode.OFF)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate devices."""
    _LOGGER.info("Setting up simple climate entities")
    
    config = hass.data[DOMAIN][config_entry.entry_id]
    controllerid = config["controller_id"]  # Use string keys instead of constants
    ipaddress = config["ip_address"]
    username = config["username"]
    password = config["password"]

    mitsubishi_ae200_functions = MitsubishiAE200Functions()
    devices = []
    
    try:
        group_list = await mitsubishi_ae200_functions.getDevicesAsync(ipaddress, username, password)
        _LOGGER.info(f"Found devices: {group_list}")
        
        for group in group_list:
            device_id = group["id"]
            device_name = group["name"]  # Use original name for now
            
            _LOGGER.info(f"Creating simple climate entity: {device_id} -> {device_name}")
            
            climate_entity = AE200Climate(
                hass, ipaddress, device_id, device_name, 
                mitsubishi_ae200_functions, username, password, controllerid
            )
            devices.append(climate_entity)

        if devices:
            async_add_entities(devices, update_before_add=True)
            _LOGGER.info(f"Added {len(devices)} simple climate entities")
        else:
            _LOGGER.warning("No devices found during setup")
            
    except Exception as exc:
        _LOGGER.error(f"Setup error: {exc}", exc_info=True)

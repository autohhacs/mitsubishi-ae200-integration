"""Simple fix focusing on temperature setting commands."""
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
        try:
            self._attributes = await self._mitsubishi_ae200_functions.getDeviceInfoAsync(
                self._ipaddress, self._deviceid, self._username, self._password
            )
            self._last_info_time_s = asyncio.get_event_loop().time()
            _LOGGER.info(f"📊 {self._name} - Current device state:")
            _LOGGER.info(f"   Drive: {self._attributes.get('Drive', 'N/A')}")
            _LOGGER.info(f"   Mode: {self._attributes.get('Mode', 'N/A')}")
            _LOGGER.info(f"   SetTemp1 (Cool): {self._attributes.get('SetTemp1', 'N/A')}")
            _LOGGER.info(f"   SetTemp2 (Heat): {self._attributes.get('SetTemp2', 'N/A')}")
            _LOGGER.info(f"   InletTemp: {self._attributes.get('InletTemp', 'N/A')}")
        except Exception as e:
            _LOGGER.error(f"❌ Failed to refresh {self._name}: {e}")
            raise

    async def _get_info(self, key, default_value):
        current_time = asyncio.get_event_loop().time()
        if not self._attributes or (current_time - self._last_info_time_s) > self._info_lease_seconds:
            await self._refresh_device_info_async()
        return self._attributes.get(key, default_value)

    async def _to_float(self, value):
        try:
            return float(value) if value is not None and str(value).strip() != "" else None
        except (ValueError, TypeError):
            return None

    def getName(self):
        return self._name

    async def getRoomTemperature(self):
        try:
            temp = await self._to_float(await self._get_info("InletTemp", None))
            return temp
        except Exception as e:
            _LOGGER.error(f"❌ Error getting room temp for {self._name}: {e}")
            return None

    async def getTargetTemperature(self):
        try:
            mode = await self.getMode()
            if mode == Mode.Heat:
                temp = await self._to_float(await self._get_info("SetTemp2", None))
            else:
                temp = await self._to_float(await self._get_info("SetTemp1", None))
            return temp
        except Exception as e:
            _LOGGER.error(f"❌ Error getting target temp for {self._name}: {e}")
            return None

    async def getMode(self):
        try:
            return await self._get_info("Mode", Mode.Auto)
        except Exception as e:
            _LOGGER.error(f"❌ Error getting mode for {self._name}: {e}")
            return Mode.Auto

    async def isPowerOn(self):
        try:
            drive_status = await self._get_info("Drive", "OFF")
            return drive_status == "ON"
        except Exception as e:
            _LOGGER.error(f"❌ Error getting power status for {self._name}: {e}")
            return False

    async def setTemperature(self, temperature):
        """Set target temperature - ENHANCED DEBUGGING."""
        try:
            _LOGGER.info(f"🌡️ === TEMPERATURE SETTING DEBUG FOR {self._name} ===")
            
            # Get current state first
            await self._refresh_device_info_async()
            mode = await self.getMode()
            is_on = await self.isPowerOn()
            
            _LOGGER.info(f"   Requested temperature: {temperature}")
            _LOGGER.info(f"   Current mode: {mode}")
            _LOGGER.info(f"   Power status: {is_on}")
            
            if not is_on:
                _LOGGER.warning("⚠️ Device is OFF - turning it ON first")
                await self.powerOn()
                await asyncio.sleep(2)
            
            # Determine which temperature field to use
            if mode == Mode.Heat:
                temp_field = "SetTemp2"
                _LOGGER.info(f"🔥 Using HEATING field: {temp_field}")
            else:
                temp_field = "SetTemp1"
                _LOGGER.info(f"❄️ Using COOLING field: {temp_field}")
            
            # Convert to integer (device expects whole numbers)
            temp_int = int(round(temperature))
            
            # Try multiple command formats to see which works
            commands_to_try = [
                {temp_field: str(temp_int)},           # "22"
                {temp_field: temp_int},                # 22
                {temp_field: f"{temp_int}.0"},         # "22.0"
            ]
            
            for i, command in enumerate(commands_to_try, 1):
                try:
                    _LOGGER.info(f"📤 Attempt {i}: Sending {command}")
                    
                    await self._mitsubishi_ae200_functions.sendAsync(
                        self._ipaddress, self._deviceid, command, 
                        self._username, self._password
                    )
                    
                    _LOGGER.info(f"✅ Command {i} sent successfully")
                    
                    # Wait and check if it worked
                    await asyncio.sleep(3)
                    await self._refresh_device_info_async()
                    
                    new_temp = await self.getTargetTemperature()
                    _LOGGER.info(f"🔍 After command {i}: Target temp is now {new_temp}")
                    
                    if new_temp and abs(new_temp - temp_int) < 1:
                        _LOGGER.info(f"🎉 SUCCESS! Command {i} worked!")
                        return
                    else:
                        _LOGGER.warning(f"⚠️ Command {i} didn't work as expected")
                        
                except Exception as e:
                    _LOGGER.error(f"❌ Command {i} failed: {e}")
            
            _LOGGER.error(f"❌ All temperature setting attempts failed for {self._name}")
            
        except Exception as e:
            _LOGGER.error(f"❌ Temperature setting error for {self._name}: {e}")
            raise

    async def setMode(self, mode):
        try:
            _LOGGER.info(f"🔧 Setting mode for {self._name}: {mode}")
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Mode": mode}, 
                self._username, self._password
            )
            self._last_info_time_s = 0
        except Exception as e:
            _LOGGER.error(f"❌ Failed to set mode for {self._name}: {e}")
            raise

    async def powerOn(self):
        try:
            _LOGGER.info(f"⚡ Powering ON {self._name}")
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Drive": "ON"}, 
                self._username, self._password
            )
            self._last_info_time_s = 0
        except Exception as e:
            _LOGGER.error(f"❌ Failed to power on {self._name}: {e}")
            raise

    async def powerOff(self):
        try:
            _LOGGER.info(f"⚡ Powering OFF {self._name}")
            await self._mitsubishi_ae200_functions.sendAsync(
                self._ipaddress, self._deviceid, {"Drive": "OFF"}, 
                self._username, self._password
            )
            self._last_info_time_s = 0
        except Exception as e:
            _LOGGER.error(f"❌ Failed to power off {self._name}: {e}")
            raise


class AE200Climate(ClimateEntity):
    def __init__(self, hass, device: AE200Device, controllerid: str, ipaddress: str, use_fahrenheit: bool = False):
        self._device = device
        self._use_fahrenheit = use_fahrenheit
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
        """Set temperature with enhanced debugging."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            _LOGGER.info(f"🌡️ HOME ASSISTANT: Setting {self.name} to {temperature}°F")
            try:
                await self._device.setTemperature(temperature)
                self._target_temperature = temperature  # Update local state
                self.async_write_ha_state()
            except Exception as e:
                _LOGGER.error(f"❌ Failed to set temperature: {e}")

    async def async_set_hvac_mode(self, hvac_mode):
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
            _LOGGER.error(f"❌ Failed to set HVAC mode: {e}")

    async def async_update(self):
        try:
            self._current_temperature = await self._device.getRoomTemperature()
            
            if await self._device.isPowerOn():
                self._target_temperature = await self._device.getTargetTemperature()
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
                    self._target_temperature = None
                elif mode == Mode.Auto:
                    self._hvac_mode = HVACMode.HEAT_COOL
                    self._last_hvac_mode = HVACMode.HEAT_COOL
            else:
                self._target_temperature = None
                self._hvac_mode = HVACMode.OFF
                
        except Exception as e:
            _LOGGER.error(f"❌ Failed to update {self.name}: {e}")

    async def async_turn_on(self):
        try:
            await self._device.powerOn()
            self._hvac_mode = self._last_hvac_mode
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"❌ Failed to turn on: {e}")

    async def async_turn_off(self):
        try:
            await self._device.powerOff()
            self._hvac_mode = HVACMode.OFF
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.error(f"❌ Failed to turn off: {e}")


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate devices."""
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
        group_list = await mitsubishi_ae200_functions.getDevicesAsync(ipaddress, username, password)
        
        for group in group_list:
            device_id = group["id"]
            device_name = device_names.get(device_id, group["name"])
            
            device = AE200Device(ipaddress, device_id, device_name, mitsubishi_ae200_functions, username, password)
            climate_entity = AE200Climate(hass, device, controllerid, ipaddress, use_fahrenheit)
            devices.append(climate_entity)

        if devices:
            async_add_entities(devices, update_before_add=True)
            _LOGGER.info(f"✅ Added {len(devices)} devices")
            
    except Exception as exc:
        _LOGGER.error(f"❌ Setup error: {exc}", exc_info=True)

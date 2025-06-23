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
    def __init__(self, ipaddress: str, deviceid: str, name: str, mitsubishi_ae200_functions: MitsubishiAE200Functions):
        self._ipaddress = ipaddress
        self._deviceid = deviceid
        self._name = name
        self._mitsubishi_ae200_functions = mitsubishi_ae200_functions
        self._attributes = {}
        self._last_info_time_s = 0
        self._info_lease_seconds = 10

    async def _refresh_device_info_async(self):
        _LOGGER.info(f"Refreshing device info: {self._ipaddress} - {self._deviceid} ({self._name})")
        self._attributes = await self._mitsubishi_ae200_functions.getDeviceInfoAsync(self._ipaddress, self._deviceid)
        self._last_info_time_s = asyncio.get_event_loop().time()
        if self._deviceid == "6":
            _LOGGER.info(self._attributes) # Only log HVAC for Library

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
        mode = await self.getMode()
        if mode == Mode.Heat:
            await self._mitsubishi_ae200_functions.sendAsync(self._ipaddress, self._deviceid, {"SetTemp2": str(temperature)})
        elif mode == Mode.Cool:
            await self._mitsubishi_ae200_functions.sendAsync(self._ipaddress, self._deviceid, {"SetTemp1": str(temperature)})
        elif mode == Mode.Dry:
            await self._mitsubishi_ae200_functions.sendAsync(self._ipaddress, self._deviceid, {"SetTemp1": str(temperature)})
        else:
            await self._mitsubishi_ae200_functions.sendAsync(self._ipaddress, self._deviceid, {"SetTemp1": str(temperature)})
            
    async def setTemperatureHigh(self,temperature):
        await self._mitsubishi_ae200_functions.sendAsync(self._ipaddress, self._deviceid, {"SetTemp1": str(temperature)})
        
    async def setTemperatureLow(self, temperature):
        await self._mitsubishi_ae200_functions.sendAsync(self._ipaddress, self._deviceid, {"SetTemp2": str(temperature)})

    async def setFanSpeed(self, speed):
        await self._mitsubishi_ae200_functions.sendAsync(self._ipaddress, self._deviceid, {"FanSpeed": speed})
        
    async def setSwingMode(self, mode):
        await self._mitsubishi_ae200_functions.sendAsync(self._ipaddress, self._deviceid, {"AirDirection": mode})

    async def setMode(self, mode):
        await self._mitsubishi_ae200_functions.sendAsync(self._ipaddress, self._deviceid, {"Mode": mode})

    async def powerOn(self):
        await self._mitsubishi_ae200_functions.sendAsync(self._ipaddress, self._deviceid, {"Drive": "ON"})

    async def powerOff(self):
        await self._mitsubishi_ae200_functions.sendAsync(self._ipaddress, self._deviceid, {"Drive": "OFF"})


class AE200Climate(ClimateEntity):
    def __init__(self, hass, device: AE200Device, controllerid: str, use_fahrenheit: bool = False):
        self._device = device
        self._use_fahrenheit = use_fahrenheit
        self.entity_id = generate_entity_id(
            "climate.{}", f"autoh_mitsubishi_ae_200_{controllerid}_{device.getName()}", None, hass
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
    
    async def async_turn_on(self):
        _LOGGER.info(f"Turning on HVAC mode: {self._last_hvac_mode} for {self.entity_id}")
        await self._device.powerOn()
        self._hvac_mode = self._last_hvac_mode
        self.async_write_ha_state()
        
    async def async_turn_off(self):
        _LOGGER.info(f"Turning off HVAC for {self.entity_id}")
        await self._device.powerOff()
        self._hvac_mode = HVACMode.OFF
        self.async_write_ha_state()
    
    async def async_set_swing_mode(self, swing_mode):
        device_swing_mode = self._reverse_swing_mode_map.get(swing_mode, swing_mode)
        _LOGGER.info(f"Setting swing mode: {device_swing_mode} for {self.entity_id}")
        await self._device.setSwingMode(device_swing_mode)
        self._swing_mode = device_swing_mode
        self.async_write_ha_state()

    async def async_set_fan_mode(self, fan_mode):
        device_fan_mode = self._reverse_fan_mode_map.get(fan_mode, fan_mode)
        _LOGGER.info(f"Setting fan mode: {device_fan_mode} for {self.entity_id}")
        await self._device.setFanSpeed(device_fan_mode)
        self._fan_mode = device_fan_mode
        self.async_write_ha_state()

    async def async_set_temperature(self, **kwargs):
        _LOGGER.info(f"Setting temperature: {kwargs.get(ATTR_TEMPERATURE)} for {self.entity_id}")
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is not None:
            # Convert to Celsius for device communication
            temp_celsius = fahrenheit_to_celsius(temperature) if self._use_fahrenheit else temperature
            await self._device.setTemperature(temp_celsius)
            self._target_temperature = temp_celsius
            self.async_write_ha_state()
            
        temp_low = kwargs.get("target_temp_low")
        temp_high = kwargs.get("target_temp_high")
        if temp_low is not None and temp_high is not None:
            # Convert to Celsius for device communication
            temp_low_celsius = fahrenheit_to_celsius(temp_low) if self._use_fahrenheit else temp_low
            temp_high_celsius = fahrenheit_to_celsius(temp_high) if self._use_fahrenheit else temp_high
            
            await self._device.setTemperatureHigh(temp_high_celsius)
            await self._device.setTemperatureLow(temp_low_celsius)
            self._target_temperature_low = temp_low_celsius
            self._target_temperature_high = temp_high_celsius
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode):
        _LOGGER.info(f"Setting HVAC mode: {hvac_mode} for {self.entity_id}")
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

    async def async_update(self):
        _LOGGER.info(f"Updating climate entity: {self.entity_id}")
        await self._device._refresh_device_info_async()
        self._current_temperature = await self._device.getRoomTemperature()
        self._fan_mode = await self._device.getFanSpeed()
        self._swing_mode = await self._device.getSwingMode()
        if await self._device.isPowerOn():
            self._target_temperature = await self._device.getTargetTemperature()
            self._target_temperature_high = await self._device.getTargetTemperatureHigh()
            self._target_temperature_low = await self._device.getTargetTemperatureLow()
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
                self._hvac_mode = HVACMode.HEAT_COOL
                self._last_hvac_mode = HVACMode.HEAT_COOL
        else:
            self._target_temperature = None
            self._target_temperature_high = None
            self._target_temperature_low = None
            self._hvac_mode = HVACMode.OFF


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

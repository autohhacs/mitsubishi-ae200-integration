"""Config flow for AutoH Mitsubishi AE200 integration."""
import logging
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.exceptions import HomeAssistantError

DOMAIN = "mitsubishi_ae200"

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("controller_id"): str,
        vol.Required("ip_address"): str,
        vol.Required("username"): str,
        vol.Required("password"): str,
        vol.Optional("temperature_unit", default="fahrenheit"): vol.In(
            ["celsius", "fahrenheit"]
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AutoH Mitsubishi AE200."""

    VERSION = 1

    def __init__(self):
        """Initialize the config flow."""
        self.discovered_devices = []
        self.config_data = {}

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            # Store the initial config
            self.config_data = user_input
            
            # Import here to avoid circular imports
            from .mitsubishi_ae200 import MitsubishiAE200Functions
            
            # Test connection and get devices
            mitsubishi_ae200_functions = MitsubishiAE200Functions()
            
            # Test authentication
            auth_success = await mitsubishi_ae200_functions.authenticate(
                user_input["ip_address"], 
                user_input["username"], 
                user_input["password"]
            )
            
            if not auth_success:
                raise InvalidAuth("Authentication failed")
            
            # Get device list
            devices = await mitsubishi_ae200_functions.getDevicesAsync(
                user_input["ip_address"],
                user_input["username"], 
                user_input["password"]
            )
            
            if not devices:
                raise CannotConnect("No devices found")
            
            self.discovered_devices = devices
            _LOGGER.info(f"Discovered {len(devices)} devices: {devices}")
            
            # If devices found, go to device naming step
            return await self.async_step_device_names()
            
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception as exc:
            _LOGGER.exception("Unexpected exception during device discovery")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_device_names(self, user_input=None):
        """Handle device naming step."""
        if user_input is None:
            # Create schema for device names
            device_schema = {}
            for device in self.discovered_devices:
                device_id = device["id"]
                device_name = device["name"]
                device_schema[vol.Optional(f"device_{device_id}_name", default=device_name)] = str
            
            data_schema = vol.Schema(device_schema)
            
            return self.async_show_form(
                step_id="device_names",
                data_schema=data_schema,
                description_placeholders={
                    "device_count": str(len(self.discovered_devices)),
                    "devices": ", ".join([f"{d['id']}: {d['name']}" for d in self.discovered_devices])
                }
            )

        # Process device names
        device_names = {}
        for device in self.discovered_devices:
            device_id = device["id"]
            custom_name = user_input.get(f"device_{device_id}_name", device["name"])
            device_names[device_id] = custom_name

        # Check if already configured
        await self.async_set_unique_id(
            f"{self.config_data['ip_address']}_{self.config_data['controller_id']}"
        )
        self._abort_if_unique_id_configured()

        # Combine all config data
        final_config = {**self.config_data, "device_names": device_names}

        return self.async_create_entry(
            title=f"AutoH Mitsubishi AE200 ({self.config_data['controller_id']})",
            data=final_config
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

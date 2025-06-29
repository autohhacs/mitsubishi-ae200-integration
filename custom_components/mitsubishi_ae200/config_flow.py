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

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            # Basic validation
            if not user_input.get("ip_address"):
                raise CannotConnect("No IP address provided")
            
            if not user_input.get("username"):
                raise InvalidAuth("No username provided")
            
            # Test connection if possible
            try:
                from .mitsubishi_ae200 import MitsubishiAE200Functions
                
                mitsubishi_ae200_functions = MitsubishiAE200Functions()
                
                # Test authentication
                auth_success = await mitsubishi_ae200_functions.authenticate(
                    user_input["ip_address"], 
                    user_input["username"], 
                    user_input["password"]
                )
                
                if not auth_success:
                    raise InvalidAuth("Authentication failed")
                
                # Test device discovery
                devices = await mitsubishi_ae200_functions.getDevicesAsync(
                    user_input["ip_address"],
                    user_input["username"], 
                    user_input["password"]
                )
                
                if not devices:
                    raise CannotConnect("No devices found")
                
                _LOGGER.info(f"Found {len(devices)} devices during setup")
                
            except ImportError:
                _LOGGER.warning("Could not import communication module - skipping connection test")
            except Exception as e:
                _LOGGER.error(f"Connection test failed: {e}")
                raise CannotConnect(f"Connection test failed: {str(e)}")
            
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception as exc:
            _LOGGER.exception("Unexpected exception during config flow")
            errors["base"] = "unknown"
        else:
            # Check if already configured
            await self.async_set_unique_id(
                f"{user_input['ip_address']}_{user_input['controller_id']}"
            )
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=f"AutoH Mitsubishi AE200 ({user_input['controller_id']})", 
                data=user_input
            )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

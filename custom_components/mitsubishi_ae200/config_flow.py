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
            # Basic validation - just check if IP is provided
            if not user_input.get("ip_address"):
                raise CannotConnect("No IP address provided")
            
            # For now, just accept the input without testing connection
            # We can add connection testing later once basic setup works
            
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception")
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

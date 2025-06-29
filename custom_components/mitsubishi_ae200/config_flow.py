"""Config flow for AutoH Mitsubishi AE200 integration."""
from __future__ import annotations
import logging
from typing import Any
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN,
    CONF_CONTROLLER_ID,
    CONF_IP_ADDRESS,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_TEMPERATURE_UNIT,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from .mitsubishi_ae200 import MitsubishiAE200Functions

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_CONTROLLER_ID): str,
        vol.Required(CONF_IP_ADDRESS): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_TEMPERATURE_UNIT, default=TEMP_FAHRENHEIT): vol.In(
            [TEMP_CELSIUS, TEMP_FAHRENHEIT]
        ),
    }
)


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.
    
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    ip_address = data[CONF_IP_ADDRESS]
    controller_id = data[CONF_CONTROLLER_ID]
    username = data[CONF_USERNAME]
    password = data[CONF_PASSWORD]
    
    mitsubishi_ae200_functions = MitsubishiAE200Functions()
    
    try:
        # Test authentication first
        auth_success = await mitsubishi_ae200_functions.authenticate(ip_address, username, password)
        if not auth_success:
            raise InvalidAuth("Authentication failed")
        
        # Test connection by getting device list
        devices = await mitsubishi_ae200_functions.getDevicesAsync(ip_address, username, password)
        if not devices:
            raise CannotConnect("No devices found")
            
    except InvalidAuth:
        raise
    except Exception as exc:
        _LOGGER.exception("Error connecting to Mitsubishi AE200 controller")
        raise CannotConnect from exc

    # Return info that you want to store in the config entry.
    return {
        "title": f"AutoH Mitsubishi AE200 ({controller_id})",
        "devices_found": len(devices),
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for AutoH Mitsubishi AE200."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            # Check if already configured
            await self.async_set_unique_id(
                f"{user_input[CONF_IP_ADDRESS]}_{user_input[CONF_CONTROLLER_ID]}"
            )
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

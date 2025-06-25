“”“Config flow for AutoH Mitsubishi AE200 integration.”””
from **future** import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
DOMAIN,
CONF_CONTROLLER_ID,
CONF_IP_ADDRESS,
CONF_TEMPERATURE_UNIT,
TEMP_CELSIUS,
TEMP_FAHRENHEIT,
)

_LOGGER = logging.getLogger(**name**)

STEP_USER_DATA_SCHEMA = vol.Schema(
{
vol.Required(CONF_CONTROLLER_ID): cv.string,
vol.Required(CONF_IP_ADDRESS): cv.string,
vol.Optional(CONF_TEMPERATURE_UNIT, default=TEMP_FAHRENHEIT): vol.In(
[TEMP_CELSIUS, TEMP_FAHRENHEIT]
),
}
)

async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
“”“Validate the user input allows us to connect.

```
Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
"""
ip_address = data[CONF_IP_ADDRESS]
controller_id = data[CONF_CONTROLLER_ID]

# Import here to avoid circular imports
from .mitsubishi_ae200 import MitsubishiAE200Functions

mitsubishi_ae200_functions = MitsubishiAE200Functions()

try:
    # Test connection by getting device list
    devices = await mitsubishi_ae200_functions.getDevicesAsync(ip_address)
    if not devices:
        raise CannotConnect("No devices found")
except Exception as exc:
    _LOGGER.exception("Error connecting to Mitsubishi AE200 controller")
    raise CannotConnect from exc

# Return info that you want to store in the config entry.
return {
    "title": f"AutoH Mitsubishi AE200 ({controller_id})",
    "devices_found": len(devices),
}
```

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
“”“Handle a config flow for AutoH Mitsubishi AE200.”””

```
VERSION = 1

async def async_step_user(
    self, user_input: dict[str, Any] | None = None
) -> FlowResult:
    """Handle the initial step."""
    errors: dict[str, str] = {}

    if user_input is not None:
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
```

class CannotConnect(HomeAssistantError):
“”“Error to indicate we cannot connect.”””

class InvalidAuth(HomeAssistantError):
“”“Error to indicate there is invalid auth.”””
“”“Config flow for AutoH Mitsubishi AE200 integration.”””
from **future** import annotations

import asyncio
import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
import homeassistant.helpers.config_validation as cv

from .const import (
DOMAIN,
CONF_CONTROLLER_ID,
CONF_TEMPERATURE_UNIT,
TEMP_CELSIUS,
TEMP_FAHRENHEIT,
)

_LOGGER = logging.getLogger(**name**)

class CannotConnect(HomeAssistantError):
“”“Error to indicate we cannot connect.”””

class MitsubishiAE200ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
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
            await self._test_connection(user_input[CONF_IP_ADDRESS])
            
            # Check if already configured
            await self.async_set_unique_id(
                f"{user_input[CONF_IP_ADDRESS]}_{user_input[CONF_CONTROLLER_ID]}"
            )
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=f"AutoH Mitsubishi AE200 ({user_input[CONF_CONTROLLER_ID]})",
                data=user_input,
            )
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

    data_schema = vol.Schema(
        {
            vol.Required(CONF_CONTROLLER_ID): cv.string,
            vol.Required(CONF_IP_ADDRESS): cv.string,
            vol.Optional(CONF_TEMPERATURE_UNIT, default=TEMP_FAHRENHEIT): vol.In(
                [TEMP_CELSIUS, TEMP_FAHRENHEIT]
            ),
        }
    )

    return self.async_show_form(
        step_id="user",
        data_schema=data_schema,
        errors=errors,
    )

async def _test_connection(self, ip_address: str) -> None:
    """Test if we can connect to the device."""
    try:
        # Import here to avoid circular imports
        from .mitsubishi_ae200 import MitsubishiAE200Functions
        
        mitsubishi_ae200_functions = MitsubishiAE200Functions()
        
        # Test connection with timeout
        devices = await asyncio.wait_for(
            mitsubishi_ae200_functions.getDevicesAsync(ip_address),
            timeout=10.0
        )
        
        if not devices:
            raise CannotConnect("No devices found")
            
        _LOGGER.info(f"Successfully connected to controller at {ip_address}, found {len(devices)} devices")
        
    except asyncio.TimeoutError:
        _LOGGER.error(f"Timeout connecting to controller at {ip_address}")
        raise CannotConnect("Connection timeout")
    except Exception as exc:
        _LOGGER.error(f"Error connecting to controller at {ip_address}: {exc}")
        raise CannotConnect from exc
```
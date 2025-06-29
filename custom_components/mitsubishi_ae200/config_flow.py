"""Minimal config flow."""
import voluptuous as vol
from homeassistant import config_entries

DOMAIN = "mitsubishi_ae200"

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("name", default="Controller"): str,
                    vol.Required("ip"): str,
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                })
            )
        
        return self.async_create_entry(
            title=f"AE200 {user_input['name']}", 
            data=user_input
        )

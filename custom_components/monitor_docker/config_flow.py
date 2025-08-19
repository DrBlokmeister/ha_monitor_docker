"""Config flow for Monitor Docker integration."""
from __future__ import annotations

from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_MONITORED_CONDITIONS, CONF_NAME, CONF_URL
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DEFAULT_NAME,
    DOMAIN,
    CONF_CONTAINERS,
    MONITORED_CONDITIONS_LIST,
)


class MonitorDockerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Monitor Docker."""

    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        if user_input is not None:
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        data_schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Optional(CONF_URL): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=data_schema)

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Handle import from configuration.yaml."""
        options = {
            key: import_config[key]
            for key in (CONF_CONTAINERS, CONF_MONITORED_CONDITIONS)
            if key in import_config
        }
        data = {key: value for key, value in import_config.items() if key not in options}
        return self.async_create_entry(
            title=data.get(CONF_NAME, DEFAULT_NAME), data=data, options=options
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return MonitorDockerOptionsFlow(config_entry)


class MonitorDockerOptionsFlow(config_entries.OptionsFlow):
    """Handle Monitor Docker options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options for Monitor Docker."""
        if user_input is not None:
            containers = [
                container.strip()
                for container in user_input.get(CONF_CONTAINERS, "").split(",")
                if container.strip()
            ]
            monitored = user_input.get(CONF_MONITORED_CONDITIONS, [])
            return self.async_create_entry(
                title="",
                data={
                    CONF_CONTAINERS: containers,
                    CONF_MONITORED_CONDITIONS: monitored,
                },
            )

        existing_containers = ", ".join(
            self.config_entry.options.get(CONF_CONTAINERS, [])
        )
        existing_monitored = self.config_entry.options.get(
            CONF_MONITORED_CONDITIONS, MONITORED_CONDITIONS_LIST
        )

        data_schema = vol.Schema(
            {
                vol.Optional(CONF_CONTAINERS, default=existing_containers): str,
                vol.Optional(CONF_MONITORED_CONDITIONS, default=existing_monitored): cv.multi_select(
                    MONITORED_CONDITIONS_LIST
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=data_schema)

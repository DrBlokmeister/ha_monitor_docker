"""Monitor Docker integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, SOURCE_IMPORT
from homeassistant.const import (
    CONF_MONITORED_CONDITIONS,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_URL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .const import (
    API,
    CONFIG,
    CONF_CERTPATH,
    CONF_CONTAINERS,
    CONF_CONTAINERS_EXCLUDE,
    CONF_MEMORYCHANGE,
    CONF_PRECISION_CPU,
    CONF_PRECISION_MEMORY_MB,
    CONF_PRECISION_MEMORY_PERCENTAGE,
    CONF_PRECISION_NETWORK_KB,
    CONF_PRECISION_NETWORK_MB,
    CONF_PREFIX,
    CONF_RENAME,
    CONF_RENAME_ENITITY,
    CONF_RETRY,
    CONF_SENSORNAME,
    CONF_SWITCHENABLED,
    CONF_SWITCHNAME,
    CONF_BUTTONENABLED,
    CONF_BUTTONNAME,
    CONTAINER_INFO_ALLINONE,
    DEFAULT_NAME,
    DEFAULT_RETRY,
    DEFAULT_SENSORNAME,
    DEFAULT_SWITCHNAME,
    DEFAULT_BUTTONNAME,
    DOMAIN,
    MONITORED_CONDITIONS_LIST,
    PRECISION,
    COMPONENTS,
)
from .helpers import DockerAPI

_LOGGER = logging.getLogger(__name__)

DEFAULT_SCAN_INTERVAL = timedelta(seconds=10)

DOCKER_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_PREFIX, default=""): cv.string,
        vol.Optional(CONF_URL, default=None): vol.Any(cv.string, None),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): cv.time_period,
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[]): vol.All(
            cv.ensure_list,
            [vol.In(MONITORED_CONDITIONS_LIST)],
        ),
        vol.Optional(CONF_CONTAINERS, default=[]): cv.ensure_list,
        vol.Optional(CONF_CONTAINERS_EXCLUDE, default=[]): cv.ensure_list,
        vol.Optional(CONF_RENAME, default={}): dict,
        vol.Optional(CONF_RENAME_ENITITY, default=False): cv.boolean,
        vol.Optional(CONF_SENSORNAME, default=DEFAULT_SENSORNAME): cv.string,
        vol.Optional(CONF_SWITCHENABLED, default=True): vol.Any(
            cv.boolean, cv.ensure_list(cv.string)
        ),
        vol.Optional(CONF_BUTTONENABLED, default=False): vol.Any(
            cv.boolean, cv.ensure_list(cv.string)
        ),
        vol.Optional(CONF_SWITCHNAME, default=DEFAULT_SWITCHNAME): cv.string,
        vol.Optional(CONF_BUTTONNAME, default=DEFAULT_BUTTONNAME): cv.string,
        vol.Optional(CONF_CERTPATH, default=""): cv.string,
        vol.Optional(CONF_RETRY, default=DEFAULT_RETRY): cv.positive_int,
        vol.Optional(CONF_MEMORYCHANGE, default=100): cv.positive_int,
        vol.Optional(CONF_PRECISION_CPU, default=PRECISION): cv.positive_int,
        vol.Optional(CONF_PRECISION_MEMORY_MB, default=PRECISION): cv.positive_int,
        vol.Optional(
            CONF_PRECISION_MEMORY_PERCENTAGE, default=PRECISION
        ): cv.positive_int,
        vol.Optional(CONF_PRECISION_NETWORK_KB, default=PRECISION): cv.positive_int,
        vol.Optional(CONF_PRECISION_NETWORK_MB, default=PRECISION): cv.positive_int,
    }
)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.All(cv.ensure_list, [vol.Any(DOCKER_SCHEMA)])}, extra=vol.ALLOW_EXTRA
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Monitor Docker component."""
    hass.data.setdefault(DOMAIN, {})

    for entry in hass.config_entries.async_entries(DOMAIN):
        await hass.config_entries.async_setup(entry.entry_id)

    if DOMAIN in config:
        for conf in config[DOMAIN]:
            hass.async_create_task(
                hass.config_entries.async_init(
                    DOMAIN, source=SOURCE_IMPORT, data=conf
                )
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Monitor Docker from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    raw_config = {**entry.data, **entry.options}
    config = DOCKER_SCHEMA(raw_config)

    if len(config[CONF_MONITORED_CONDITIONS]) == 0:
        config[CONF_MONITORED_CONDITIONS] = MONITORED_CONDITIONS_LIST.copy()
        config[CONF_MONITORED_CONDITIONS].remove(CONTAINER_INFO_ALLINONE)

    if (
        len(config[CONF_MONITORED_CONDITIONS]) == 1
        and CONTAINER_INFO_ALLINONE in config[CONF_MONITORED_CONDITIONS]
    ):
        config[CONF_MONITORED_CONDITIONS] = list(MONITORED_CONDITIONS_LIST) + [
            CONTAINER_INFO_ALLINONE
        ]

    api = DockerAPI(hass, config)
    await api.init()

    hass.data[DOMAIN][entry.entry_id] = {API: api, CONFIG: config}

    await hass.config_entries.async_forward_entry_setups(entry, COMPONENTS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Monitor Docker config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, COMPONENTS)
    if unload_ok:
        api = hass.data[DOMAIN].pop(entry.entry_id)[API]
        api._dockerStopped = True
    return unload_ok


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry data to new version."""
    version = entry.version

    if version > 1:
        return True

    _LOGGER.debug("Migrating config entry from version %s", version)

    data = {k: v for k, v in entry.data.items() if k not in (CONF_CONTAINERS, CONF_MONITORED_CONDITIONS)}
    options = dict(entry.options)

    for key in (CONF_CONTAINERS, CONF_MONITORED_CONDITIONS):
        if key in entry.data and key not in options:
            options[key] = entry.data[key]

    entry.version = 2
    hass.config_entries.async_update_entry(entry, data=data, options=options)
    _LOGGER.info("Migrated Monitor Docker config entry from version %s to %s", version, entry.version)

    return True

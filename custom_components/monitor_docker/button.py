"""Monitor Docker button component."""

import asyncio
import logging
import re
from typing import Any

import voluptuous as vol
from custom_components.monitor_docker.helpers import DockerAPI, DockerContainerAPI
from homeassistant.components.button import ENTITY_ID_FORMAT, ButtonEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import slugify
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntryType, async_get as async_get_dev_reg

from .const import (
    API,
    ATTR_NAME,
    ATTR_SERVER,
    CONF_CONTAINERS,
    CONF_CONTAINERS_EXCLUDE,
    CONF_PREFIX,
    CONF_RENAME,
    CONF_RENAME_ENITITY,
    CONF_BUTTONENABLED,
    CONF_BUTTONNAME,
    CONFIG,
    CONTAINER,
    CONTAINER_INFO_STATE,
    CONTAINER_INFO_IMAGE,
    CONTAINER_INFO_IMAGE_HASH,
    DOMAIN,
    SERVICE_RESTART,
)

SERVICE_RESTART_SCHEMA = vol.Schema({ATTR_NAME: cv.string, ATTR_SERVER: cv.string})

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
):
    """Set up the Monitor Docker Button."""

    async def async_restart(parm) -> None:
        cname = parm.data[ATTR_NAME]
        cserver = parm.data.get(ATTR_SERVER, None)

        server_name = name
        if cserver is not None:
            if cserver not in hass.data[DOMAIN]:
                _LOGGER.error("Server '%s' is not configured", cserver)
                return
            else:
                server_name = cserver

        server_config = hass.data[DOMAIN][server_name][CONFIG]
        server_api = hass.data[DOMAIN][server_name][API]

        if len(server_config[CONF_CONTAINERS]) == 0:
            if server_api.get_container(cname):
                await server_api.get_container(cname).restart()
            else:
                _LOGGER.error(
                    "Service restart failed, container '%s'does not exist", cname
                )
        elif cname in server_config[CONF_CONTAINERS]:
            _LOGGER.debug("Trying to restart container '%s'", cname)
            if server_api.get_container(cname):
                await server_api.get_container(cname).restart()
            else:
                _LOGGER.error(
                    "Service restart failed, container '%s'does not exist", cname
                )
        else:
            _LOGGER.error(
                "Service restart failed, container '%s' is not configured", cname
            )

    def find_rename(d: dict[str, str], item: str) -> str:
        for k in d:
            if re.match(k, item):
                return d[k]

        return item

    if discovery_info is None:
        return

    instance = discovery_info[CONF_NAME]
    name = discovery_info[CONF_NAME]
    api = hass.data[DOMAIN][name][API]
    config = hass.data[DOMAIN][name][CONFIG]

    # Set or overrule prefix
    prefix = name
    if config[CONF_PREFIX]:
        prefix = config[CONF_PREFIX]

    # Don't create any butoon if disabled
    if config[CONF_BUTTONENABLED] == False:
        _LOGGER.debug("[%s]: Button(s) are disabled", instance)
        return True

    _LOGGER.debug("[%s]: Setting up button(s)", instance)

    buttons = []

    # We support add/re-add of a container
    if CONTAINER in discovery_info:
        clist = [discovery_info[CONTAINER]]
    else:
        clist = api.list_containers()

    for cname in clist:
        includeContainer = False
        if cname in config[CONF_CONTAINERS] or not config[CONF_CONTAINERS]:
            includeContainer = True

        if config[CONF_CONTAINERS_EXCLUDE] and cname in config[CONF_CONTAINERS_EXCLUDE]:
            includeContainer = False

        if includeContainer:
            if (
                config[CONF_BUTTONENABLED] == True
                or cname in config[CONF_BUTTONENABLED]
            ):
                _LOGGER.debug("[%s] %s: Adding component Button", instance, cname)

                # Only force rename of entityid is requested, to not break backwards compatibility
                alias_entityid = cname
                if config[CONF_RENAME_ENITITY]:
                    alias_entityid = find_rename(config[CONF_RENAME], cname)

                buttons.append(
                    DockerContainerButton(
                        api.get_container(cname),
                        instance=instance,
                        prefix=prefix,
                        cname=cname,
                        alias_entityid=alias_entityid,
                        alias_name=find_rename(config[CONF_RENAME], cname),
                        name_format=config[CONF_BUTTONNAME],
                    )
                )
            else:
                _LOGGER.debug("[%s] %s: NOT Adding component Button", instance, cname)

    if not buttons:
        _LOGGER.info("[%s]: No containers set-up", instance)
        return False

    entity_registry = er.async_get(hass)
    device_registry = async_get_dev_reg(hass)
    for entity in buttons:
        if (entry := entity_registry.async_get(entity.entity_id)) and not entry.unique_id:
            device = device_registry.async_get_device(
                entity.device_info["identifiers"], set()
            )
            if device is None:
                device = device_registry.async_get_or_create(
                    config_entry_id=None, **entity.device_info
                )
            entity_registry.async_update_entity(
                entry.entity_id, new_unique_id=entity.unique_id, device_id=device.id
            )

    async_add_entities(buttons, True)

    # platform = entity_platform.current_platform.get()
    # platform.async_register_entity_service(SERVICE_RESTART, {}, "async_restart")
    hass.services.async_register(
        DOMAIN, SERVICE_RESTART, async_restart, schema=SERVICE_RESTART_SCHEMA
    )

    return True

#################################################################
class DockerContainerButton(ButtonEntity):
    def __init__(
        self, 
        container: DockerContainerAPI,
        instance: str,
        prefix: str,
        cname: str,
        alias_entityid: str,
        alias_name: str,
        name_format: str,
    ):
        self._container = container
        self._instance = instance
        self._prefix = prefix
        self._cname = cname
        self._state = False
        self._entity_id = ENTITY_ID_FORMAT.format(
            slugify(self._prefix + "_" + self._cname + "_restart")
        )
        self._name = name_format.format(name=alias_name)
        self._removed = False

    @property
    def unique_id(self) -> str:
        return f"{self._container.get_id()}_restart"

    @property
    def device_info(self) -> dict:
        info = self._container.get_info()
        return {
            "identifiers": {(DOMAIN, self._container.get_id())},
            "name": self._cname,
            "manufacturer": "Docker",
            "model": info.get(CONTAINER_INFO_IMAGE),
            "sw_version": info.get(CONTAINER_INFO_IMAGE_HASH),
            "entry_type": DeviceEntryType.SERVICE,
        }

    @property
    def entity_id(self) -> str:
        """Return the entity id of the button."""
        return self._entity_id

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def icon(self) -> str:
        return "mdi:docker"

    @property
    def extra_state_attributes(self) -> dict:
        return {}

    @property
    def is_on(self) -> bool:
        return self._state
                                 
    async def async_press(self, **kwargs: Any) -> None:
        await self._container.restart()
        self._state = False
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._container.register_callback(self.event_callback, "button")

        # Call event callback for possible information available
        self.event_callback()

    def event_callback(self, name="", remove=False) -> None:
        """Callback for update of container information."""

        if remove:
            # If already called before, do not remove it again
            if self._removed:
                return

            _LOGGER.info("[%s] %s: Removing button entity", self._instance, self._cname)
            asyncio.create_task(self.async_remove())
            self._removed = True
            return

        state = None

        try:
            info = self._container.get_info()
        except Exception as err:
            _LOGGER.error(
                "[%s] %s: Cannot request container info (%s)",
                self._instance,
                name,
                str(err),
            )
        else:
            if info is not None:
                state = info.get(CONTAINER_INFO_STATE) == "running"

        if state is not self._state:
            self._state = state
            self.async_schedule_update_ha_state()

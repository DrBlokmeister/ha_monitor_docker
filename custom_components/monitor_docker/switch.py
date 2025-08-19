"""Monitor Docker switch component."""

import logging
import re
from typing import Any

import voluptuous as vol
from custom_components.monitor_docker.helpers import DockerAPI, DockerContainerAPI
from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import slugify

from .const import (
    API,
    ATTR_NAME,
    ATTR_SERVER,
    CONF_CONTAINERS,
    CONF_CONTAINERS_EXCLUDE,
    CONF_PREFIX,
    CONF_RENAME,
    CONF_RENAME_ENITITY,
    CONF_SWITCHENABLED,
    CONF_SWITCHNAME,
    CONFIG,
    CONTAINER_INFO_IMAGE,
    CONTAINER_INFO_IMAGE_HASH,
    CONTAINER_INFO_STATE,
    DOMAIN,
    SERVICE_RESTART,
)
from .entity import DockerBaseEntity

SERVICE_RESTART_SCHEMA = vol.Schema({ATTR_NAME: cv.string, ATTR_SERVER: cv.string})

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> bool:
    """Set up the Monitor Docker Switch."""

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
                    "Service restart failed, container '%s' does not exist", cname
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

    data = hass.data[DOMAIN][entry.entry_id]
    config = data[CONFIG]
    api: DockerAPI = data[API]
    host_uid: str = data["host_uid"]
    coordinator = data["coordinator"]
    instance: str = config[CONF_NAME]
    name: str = config[CONF_NAME]

    prefix = config[CONF_PREFIX] if config[CONF_PREFIX] else instance

    if config[CONF_SWITCHENABLED] is False:
        _LOGGER.debug("[%s]: Switch(es) are disabled", instance)
        return True

    _LOGGER.debug("[%s]: Setting up switch(es)", instance)

    switches = []

    clist = api.list_containers()

    for cname in clist:
        includeContainer = False
        if cname in config[CONF_CONTAINERS] or not config[CONF_CONTAINERS]:
            includeContainer = True

        if config[CONF_CONTAINERS_EXCLUDE] and cname in config[CONF_CONTAINERS_EXCLUDE]:
            includeContainer = False

        if includeContainer:
            if (
                config[CONF_SWITCHENABLED] == True
                or cname in config[CONF_SWITCHENABLED]
            ):
                _LOGGER.debug("[%s] %s: Adding component Switch", instance, cname)

                alias_entityid = cname
                if config[CONF_RENAME_ENITITY]:
                    alias_entityid = find_rename(config[CONF_RENAME], cname)

                switches.append(
                    DockerContainerSwitch(
                        coordinator,
                        host_uid,
                        api.get_container(cname),
                        instance=instance,
                        prefix=prefix,
                        cname=cname,
                        alias_entityid=alias_entityid,
                        alias_name=find_rename(config[CONF_RENAME], cname),
                        name_format=config[CONF_SWITCHNAME],
                    )
                )
            else:
                _LOGGER.debug("[%s] %s: NOT Adding component Switch", instance, cname)

    if not switches:
        _LOGGER.info("[%s]: No containers set-up", instance)
        return False

    async_add_entities(switches, True)

    hass.services.async_register(
        DOMAIN, SERVICE_RESTART, async_restart, schema=SERVICE_RESTART_SCHEMA
    )

    return True


class DockerContainerSwitch(DockerBaseEntity, SwitchEntity):
    def __init__(
        self,
        coordinator,
        host_uid: str,
        container: DockerContainerAPI,
        instance: str,
        prefix: str,
        cname: str,
        alias_entityid: str,
        alias_name: str,
        name_format: str,
    ) -> None:
        DockerBaseEntity.__init__(self, coordinator, host_uid, container, alias_name)
        self._container = container
        self._instance = instance
        self._prefix = prefix
        self._cname = cname
        self._alias = alias_name
        self._state = False
        self._entity_id = ENTITY_ID_FORMAT.format(
            slugify(f"{self._prefix}_{alias_entityid}")
        )
        self._attr_name = name_format.format(name=alias_name)
        cid_short = container.id[:12]
        self._attr_unique_id = f"{host_uid}:{cid_short}:switch"
        self._removed = False

    @property
    def entity_id(self) -> str:
        """Return the entity id of the switch."""
        return self._entity_id

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

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._container.start()
        self._state = True
        self.async_schedule_update_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._container.stop()
        self._state = False
        self.async_schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self._container.register_callback(self.event_callback, "switch")

        # Call event callback for possible information available
        self.event_callback()

    def event_callback(self, name="", remove=False) -> None:
        """Callback for update of container information."""

        if remove:
            # If already called before, do not remove it again
            if self._removed:
                return

            _LOGGER.info("[%s] %s: Removing switch entity", self._instance, self._cname)
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

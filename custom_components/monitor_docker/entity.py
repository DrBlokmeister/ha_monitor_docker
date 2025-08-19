"""Base entity for Monitor Docker."""

from __future__ import annotations

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN, CONTAINER_INFO_IMAGE, CONTAINER_INFO_IMAGE_HASH
from .helpers import DockerContainerAPI


class DockerBaseEntity(CoordinatorEntity):
    """Base entity for Docker devices.

    Parameters
    ----------
    coordinator : DataUpdateCoordinator
        Update coordinator for the entity.
    host_uid : str
        Unique identifier for the monitored host.
    container : DockerContainerAPI | None, optional
        Container API instance, by default None.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        host_uid: str,
        container: DockerContainerAPI | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__(coordinator)
        self._host_uid = host_uid
        self._container = container
        self._name = name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information for HA."""
        if self._container is None:
            return DeviceInfo(
                identifiers={(DOMAIN, self._host_uid)},
                manufacturer="Docker",
                model="Remote Engine",
                name=self._name,
            )
        info = self._container.get_info()
        cid_short = self._container.id[:12]
        model = info.get(CONTAINER_INFO_IMAGE) or "container"
        sw = info.get(CONTAINER_INFO_IMAGE_HASH)
        sw_short = sw[:12] if isinstance(sw, str) else None
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._host_uid}:{cid_short}")},
            via_device=(DOMAIN, self._host_uid),
            manufacturer="Docker",
            model=model,
            name=self._name,
            sw_version=sw_short,
        )

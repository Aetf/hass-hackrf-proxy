"""Whether there is a connection to the daemon at all."""

from __future__ import annotations

from typing import override

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HackrfProxyConfigEntry
from hackrf_proxy_client import ProxyClient
from .entity import ProxyDiagnosticEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HackrfProxyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the connectivity sensor."""
    async_add_entities([ProxyConnection(entry, entry.runtime_data)])


class ProxyConnection(ProxyDiagnosticEntity, BinarySensorEntity):
    """Whether the WebSocket to the daemon is up."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, entry: HackrfProxyConfigEntry, client: ProxyClient) -> None:
        """Initialize the sensor."""
        super().__init__(entry, client, "connection")

    @property
    @override
    def is_on(self) -> bool:
        """Whether the daemon is connected.

        Not the same question as the transmitter's availability, which also
        goes false for a faulted radio on a perfectly good connection. Telling
        those two apart is most of what diagnosing this is.
        """
        return self.client.connected_since is not None

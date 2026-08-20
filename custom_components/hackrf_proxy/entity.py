"""Shared base for the daemon's diagnostic entities."""

from __future__ import annotations

from hackrf_proxy_client import ProxyClient
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class ProxyDiagnosticEntity(Entity):
    """An entity describing the daemon rather than controlling anything.

    Available even when the daemon is not, which is the opposite of the
    transmitter entity and is the point of these. Going dark alongside the
    thing they describe would hide them exactly when the connection has failed
    and somebody is looking for why.
    """

    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry, client: ProxyClient, key: str) -> None:
        """Initialize the entity."""
        self.client = client
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def available(self) -> bool:
        """Always. See the class docstring."""
        return True

    async def async_added_to_hass(self) -> None:
        """Follow anything the client observes."""
        await super().async_added_to_hass()

        @callback
        def updated() -> None:
            self.async_write_ha_state()

        self.async_on_remove(self.client.add_update_listener(updated))

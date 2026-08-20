"""What the daemon and its radio have been doing.

Split by where the reading comes from, and the split is deliberate. The ones
sourced from the client keep working through an outage, because an outage is
when they are read. The ones sourced from the daemon's counters go unknown,
because during an outage that is the truth about them.
"""

from __future__ import annotations

from datetime import datetime
from typing import override

from hackrf_proxy_client import ProxyClient
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import HackrfProxyConfigEntry
from .const import DOMAIN
from .coordinator import ProxyCoordinator
from .entity import ProxyDiagnosticEntity

#: What the daemon can report the radio as doing, plus the one state it cannot
#: report because reporting requires a connection.
_DISCONNECTED = "disconnected"
RADIO_STATES = ["receiving", "transmitting", "idle", "faulted", _DISCONNECTED]

#: The daemon's counters, as entities: key, translation key, and whether a
#: rising number is bad. Kept as a table because they are the same entity four
#: times over and writing four near-identical classes invites them to drift.
_COUNTERS: list[tuple[str, str]] = [
    ("rx_frames", "frames_received"),
    ("transmissions", "transmissions"),
    ("device_faults", "radio_faults"),
    ("burst_overflows", "discarded_bursts"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HackrfProxyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the diagnostics."""
    client = entry.runtime_data
    coordinator = ProxyCoordinator(hass, client)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities(
        [
            ProxyRadioState(entry, client),
            ProxyLastFrame(entry, client),
            ProxyConnectedSince(entry, client),
            ProxyDisconnects(entry, client),
            *(
                ProxyCounter(entry, coordinator, field, key)
                for field, key in _COUNTERS
            ),
        ]
    )


class ProxyRadioState(ProxyDiagnosticEntity, SensorEntity):
    """What the radio is doing, or that nothing can be asked."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = RADIO_STATES

    def __init__(self, entry: HackrfProxyConfigEntry, client: ProxyClient) -> None:
        """Initialize the sensor."""
        super().__init__(entry, client, "radio_state")

    @property
    @override
    def native_value(self) -> str:
        """The radio's state, with `disconnected` for having no answer.

        The transmitter entity going unavailable says something is wrong and
        nothing about which of the two possible somethings it is. A daemon that
        is unreachable and a radio that has faulted behind a healthy daemon
        want completely different responses, and this is where they are told
        apart.
        """
        return self.client.state or _DISCONNECTED


class ProxyLastFrame(ProxyDiagnosticEntity, SensorEntity):
    """When the receiver last heard anything."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, entry: HackrfProxyConfigEntry, client: ProxyClient) -> None:
        """Initialize the sensor."""
        super().__init__(entry, client, "last_frame")

    @property
    @override
    def native_value(self) -> datetime | None:
        """The last frame heard, over the whole band rather than any protocol.

        A receiver that has gone deaf — the radio moved, the antenna came off,
        the gain is wrong — looks from every other reading exactly like a quiet
        room. This is the one that tells them apart, and it counts every burst
        the detector sliced, not just the ones a consumer recognised.
        """
        return self.client.last_rx_frame


class ProxyConnectedSince(ProxyDiagnosticEntity, SensorEntity):
    """When the current connection was established."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, entry: HackrfProxyConfigEntry, client: ProxyClient) -> None:
        """Initialize the sensor."""
        super().__init__(entry, client, "connected_since")

    @property
    @override
    def native_value(self) -> datetime | None:
        """When this connection started, or unknown while there is none.

        Reads as a constant while things are well and as a clock that keeps
        resetting while they are not, which is the whole diagnosis for a link
        that reconnects quietly enough that nothing else notices.
        """
        return self.client.connected_since


class ProxyDisconnects(ProxyDiagnosticEntity, SensorEntity):
    """How many established connections have dropped."""

    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(self, entry: HackrfProxyConfigEntry, client: ProxyClient) -> None:
        """Initialize the sensor."""
        super().__init__(entry, client, "disconnections")

    @property
    @override
    def native_value(self) -> int:
        """The count since Home Assistant started.

        Only connections that were actually established are counted. A daemon
        that is simply not running yet would otherwise add one per backoff
        interval and read as a flapping link, which is a different problem
        needing a different fix.
        """
        return self.client.disconnects


class ProxyCounter(CoordinatorEntity[ProxyCoordinator], SensorEntity):
    """One of the counters the daemon keeps.

    A `CoordinatorEntity` rather than a [`ProxyDiagnosticEntity`], and so the
    one kind here that *does* go unavailable with the daemon. That is not an
    inconsistency: the readings above describe the connection and stay
    meaningful without one, while these are numbers only the daemon knows.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.TOTAL_INCREASING

    def __init__(
        self,
        entry: HackrfProxyConfigEntry,
        coordinator: ProxyCoordinator,
        field: str,
        key: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._field = field
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}
        )

    @property
    @override
    def native_value(self) -> int | None:
        """The counter, or unknown while the daemon cannot be asked.

        Counted by the daemon and so reset when it restarts, which
        `TOTAL_INCREASING` handles: a drop is read as a new run rather than as
        the number going backwards.
        """
        # Typed non-optional upstream, but None before the first refresh.
        if self.coordinator.data is None:  # pyright: ignore[reportUnnecessaryComparison]
            return None
        return self.coordinator.data.get("counters", {}).get(self._field)

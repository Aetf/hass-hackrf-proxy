"""Radio frequency transmitter platform for HackRF Proxy."""

from __future__ import annotations

import logging
from typing import override

from rf_protocols import RadioFrequencyCommand

from homeassistant.components.radio_frequency import RadioFrequencyTransmitterEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import HackrfProxyConfigEntry
from .client import ProxyClient, ProxyError
from .const import DOMAIN, FREQUENCY_RANGE

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HackrfProxyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the transmitter for a config entry."""
    async_add_entities([HackrfProxyTransmitter(entry)])


class HackrfProxyTransmitter(RadioFrequencyTransmitterEntity):
    """A hackrf-proxyd daemon, as a transmitter."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, entry: HackrfProxyConfigEntry) -> None:
        """Initialize the entity."""
        self._client: ProxyClient = entry.runtime_data
        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="Great Scott Gadgets",
            model=self._client.device or "HackRF",
            configuration_url=self._client.url,
        )

    @property
    @override
    def supported_frequency_ranges(self) -> list[tuple[int, int]]:
        """Return the radio's tuning range.

        The whole 1 MHz–6 GHz span, because that is what the hardware does.
        Narrowing it to the ISM bands would hide this transmitter from a
        consumer that needs anything else.
        """
        return [FREQUENCY_RANGE]

    @property
    @override
    def available(self) -> bool:
        """Whether the daemon is reachable and its radio is working.

        Follows the radio, not just the socket: the daemon keeps serving with a
        faulted radio, and a transmitter that cannot transmit is not available
        in any sense a consumer cares about.
        """
        return self._client.available

    @override
    async def async_send_command(self, command: RadioFrequencyCommand) -> None:
        """Forward an OOK command to the daemon."""
        timings = command.get_raw_timings()
        _LOGGER.debug(
            "transmitting %d timings on %d Hz (repeat=%d)",
            len(timings),
            command.frequency,
            command.repeat_count,
        )
        try:
            await self._client.async_transmit(
                frequency=command.frequency,
                timings=timings,
                repeat=command.repeat_count,
                output_power=command.output_power,
            )
        except ProxyError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="transmit_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    @override
    async def async_added_to_hass(self) -> None:
        """Republish state whenever the daemon or its radio comes and goes."""
        await super().async_added_to_hass()

        @callback
        def availability_changed(_available: bool) -> None:
            self.async_write_ha_state()

        self.async_on_remove(self._client.add_availability_listener(availability_changed))

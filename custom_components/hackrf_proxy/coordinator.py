"""Polls the daemon for the counters only it keeps.

Most of what the diagnostics show arrives by itself: the daemon pushes a
`device_state` event whenever the radio changes what it is doing, and an
`rx_frame` for everything it hears. Four numbers do not — how many frames and
transmissions it has handled, how many times it has had to reopen a faulted
radio, and how many bursts it threw away for having more edges than a frame can
hold. Those live in the daemon and have to be asked for.

Asking is cheap: `status` is answered from the engine's own bookkeeping and
touches neither the radio nor the air.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from hackrf_proxy_client import ProxyClient, ProxyError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

#: Counters move slowly and nothing acts on them, so this is as often as is
#: worth asking. The live half of the diagnostics is pushed and does not wait
#: for it.
_SCAN_INTERVAL = timedelta(seconds=60)


class ProxyCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Keeps the daemon's counters current."""

    def __init__(self, hass: HomeAssistant, client: ProxyClient) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="hackrf-proxyd status",
            update_interval=_SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        """Ask the daemon for its status."""
        try:
            return await self.client.async_status()
        except ProxyError as err:
            # The counters genuinely are unknown while the daemon is
            # unreachable, and saying so is right. The diagnostics that answer
            # *why* it is unreachable are deliberately not sourced from here,
            # so they keep reading through the outage.
            raise UpdateFailed(str(err)) from err

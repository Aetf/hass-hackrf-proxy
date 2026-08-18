"""The HackRF Proxy integration.

Presents a hackrf-proxyd daemon to Home Assistant as a radio frequency
transmitter. It carries no appliance knowledge: consumers such as `proflame`
build the timings, this forwards them to the radio.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .client import ProxyClient
from .const import SIGNAL_RX_FRAME

type HackrfProxyConfigEntry = ConfigEntry[ProxyClient]

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.RADIO_FREQUENCY,
    Platform.SENSOR,
]

#: How long to wait for the daemon on setup before deciding it is not ready.
SETUP_TIMEOUT = 10.0


async def async_setup_entry(hass: HomeAssistant, entry: HackrfProxyConfigEntry) -> bool:
    """Set up HackRF Proxy from a config entry."""

    def forward_rx_frame(frame: dict) -> None:
        # Interim bridge until an upstream receiver platform exists: consumers
        # subscribe to this signal to see what the radio hears. The payload is
        # the daemon's `rx_frame` verbatim, which is deliberately the shape a
        # future receiver entity would carry.
        async_dispatcher_send(hass, SIGNAL_RX_FRAME.format(entry.entry_id), frame)

    client = ProxyClient(
        async_get_clientsession(hass),
        entry.data[CONF_HOST],
        entry.data[CONF_PORT],
        on_rx_frame=forward_rx_frame,
    )
    await client.async_start()

    try:
        await client.async_wait_connected(SETUP_TIMEOUT)
    except TimeoutError as err:
        await client.async_stop()
        raise ConfigEntryNotReady(f"{client.url} did not answer") from err

    entry.runtime_data = client
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: HackrfProxyConfigEntry
) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.async_stop()
    return unloaded

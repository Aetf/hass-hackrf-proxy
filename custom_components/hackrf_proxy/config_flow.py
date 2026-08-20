"""Config flow for the HackRF Proxy integration."""

from __future__ import annotations

import asyncio
from typing import Any, override

import aiohttp
import voluptuous as vol
from hackrf_proxy_client import PROTOCOL_VERSION
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DEFAULT_PORT, DOMAIN

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
    }
)


class HackrfProxyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HackRF Proxy."""

    VERSION = 1

    @override
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            self._async_abort_entries_match({CONF_HOST: host, CONF_PORT: port})

            status = await _async_probe(self.hass, host, port)
            if status is None:
                errors["base"] = "cannot_connect"
            elif status.get("protocol_version") != PROTOCOL_VERSION:
                errors["base"] = "unsupported_version"
            else:
                return self.async_create_entry(
                    title=f"HackRF Proxy ({host})", data=user_input
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_SCHEMA, user_input
            ),
            errors=errors,
        )


async def _async_probe(hass: HomeAssistant, host: str, port: int) -> dict[str, Any] | None:
    """Ask a daemon for its status, or return None if it cannot be reached.

    Deliberately a plain request rather than starting the reconnecting client:
    a config flow should fail fast and say so, not sit in a retry loop. The
    timeout bounds the whole probe, handshake included.
    """
    session = async_get_clientsession(hass)
    try:
        async with (
            asyncio.timeout(10),
            session.ws_connect(f"ws://{host}:{port}") as socket,
        ):
            await socket.send_json({"v": PROTOCOL_VERSION, "id": "probe", "type": "status"})
            async for message in socket:
                if message.type is not aiohttp.WSMsgType.TEXT:
                    continue
                payload: dict[str, Any] = message.json()
                if payload.get("id") == "probe":
                    return payload
    except (aiohttp.ClientError, OSError, TimeoutError, ValueError):
        return None
    return None

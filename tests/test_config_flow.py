"""The config flow: probe outcomes decide everything, so they are what to test."""

from unittest.mock import patch

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hackrf_proxy.const import DOMAIN

from pytest_homeassistant_custom_component.common import MockConfigEntry

GOOD_STATUS = {
    "type": "status",
    "protocol_version": 1,
    "state": "receiving",
    "device": "HackRF One r9",
    "daemon_version": "0.1.0",
}
USER_INPUT = {CONF_HOST: "radio.local", CONF_PORT: 8765}


async def test_a_reachable_daemon_creates_the_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "custom_components.hackrf_proxy.config_flow._async_probe",
        return_value=GOOD_STATUS,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "HackRF Proxy (radio.local)"
    assert result["data"] == USER_INPUT


async def test_an_unreachable_daemon_shows_cannot_connect(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "custom_components.hackrf_proxy.config_flow._async_probe", return_value=None
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_a_wrong_protocol_version_is_refused_by_name(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    with patch(
        "custom_components.hackrf_proxy.config_flow._async_probe",
        return_value={**GOOD_STATUS, "protocol_version": 999},
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unsupported_version"}


async def test_the_same_daemon_cannot_be_added_twice(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, data=USER_INPUT).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

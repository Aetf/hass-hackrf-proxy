# HackRF Proxy for Home Assistant

[![CI](https://github.com/Aetf/hass-hackrf-proxy/actions/workflows/ci.yml/badge.svg)](https://github.com/Aetf/hass-hackrf-proxy/actions/workflows/ci.yml)
[![HACS](https://img.shields.io/badge/HACS-custom-41BDF5)](https://hacs.xyz/)

A custom integration that presents a [hackrf-proxyd](https://github.com/Aetf/hackrf-proxy)
daemon as a `radio_frequency` transmitter entity. It forwards raw OOK timings
and nothing else, so any consumer for any appliance on any frequency the
HackRF can reach will find it.

    supported_frequency_ranges = [(1_000_000, 6_000_000_000)]

The whole tuning range on purpose. Narrowing it to the ISM bands, as a
fixed-function transmitter would, hides this one from consumers that need
anything else — and the point of a software radio is that it does not care.

Requires Home Assistant **2026.5 or later** (the `radio_frequency` platform)
and a running [hackrf-proxyd](https://github.com/Aetf/hackrf-proxy) daemon on
the network. The daemon speaks to the same-major version of
[hackrf-proxy-client](https://pypi.org/project/hackrf-proxy-client/), which
this integration pip-installs via its manifest.

## Installing

[![Open this repository inside HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Aetf&repository=hass-hackrf-proxy&category=integration)

Via [HACS](https://hacs.xyz/): add `https://github.com/Aetf/hass-hackrf-proxy`
as a custom repository (category: integration), install, and restart Home
Assistant. Manual alternative: copy `custom_components/hackrf_proxy/` into
your config's `custom_components/` and restart.

[![Start the config flow in your Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=hackrf_proxy)

Then add **HackRF Proxy** from Settings → Devices & services. It asks for the
daemon's host and port, and refuses to finish if it cannot get a `status`
back or if the protocol versions disagree.

## Design notes

### Why WebSocket rather than MQTT

The platform's contract decides it: `async_send_command` must raise
`HomeAssistantError` **if transmission fails**, so the caller has to learn the
outcome of its own request. That is request/reply, which the daemon's
WebSocket protocol answers directly — the reply arrives when the air time is
over and carries either the duration or the reason it failed.

MQTT would need MQTT 5 response topics and correlation data, or a hand-rolled
equivalent, to say the same thing — and it would put a broker in the control
path, so a broker restart would take the appliance with it. MQTT's real
advantage, discovery without a custom integration, is not available here
anyway: it would require the daemon to publish appliance semantics, which is
exactly the layering this project exists to avoid.

### Availability follows the radio, not the socket

The daemon keeps serving with a faulted radio, so a connected socket is not
evidence that anything can be transmitted. The client marks itself
unavailable on a `device_state` of `faulted`, and only marks itself available
once the daemon has actually answered a `status` request — a TCP connection
to a wedged daemon would otherwise look healthy.

### Diagnostics, split by what survives an outage

Nine entities, all in the diagnostic category, and the split between them is
the design rather than an accident of where the data happened to live.

| Entity | Source | During an outage |
|--------|--------|------------------|
| `binary_sensor` connectivity | the client | readable |
| `sensor` enum — what the radio is doing | pushed `device_state` | reads `disconnected` |
| `sensor` timestamp — last frame heard | pushed `rx_frame` | readable |
| `sensor` timestamp — connected since | the client | unknown, which is the answer |
| `sensor` count — disconnections | the client | readable |
| `sensor` ×4 — frames, transmissions, radio faults, discarded bursts | polled `status` | unknown |

The first five keep reading through an outage, because an outage is when they
are read. The four counters go unknown, because during an outage that is the
truth about them.

**The enum is the one that earns its place.** The transmitter going
unavailable says something is wrong and nothing about which something: a
daemon that cannot be reached and a radio that has faulted behind a healthy
daemon look identical from there and want completely different responses.
`disconnected` is not a state the daemon can report — reporting requires a
connection — so the client supplies it.

**Last frame heard is the RX path's only witness.** A receiver that has
gone deaf — the radio moved, the antenna came off, the gain is wrong — looks
from every other reading exactly like a quiet room. It counts every burst the
detector sliced, not only frames a consumer recognized, so it stays honest
about the radio rather than about any one consumer.

Only `status` is polled, once a minute, and it is answered from the daemon's
own bookkeeping without touching the radio or the air.

## Receiving, and the roadmap

Transmitting rides the standard: the entity is an ordinary `radio_frequency`
transmitter, and any consumer integration finds it the ordinary way.
**Receiving does not, yet, because Home Assistant has nothing to ride** — the
`radio_frequency` platform is transmit-only so far, with a receiver platform
sketched upstream ([architecture #1365]) but not built.

Until it exists, this integration bridges the gap itself: every frame the
daemon hears is re-broadcast on the dispatcher signal
`hackrf_proxy_rx_frame_{entry_id}`, with the daemon's `rx_frame` payload
verbatim. Two things about that bridge are deliberate:

- **It is a private contract, and documented as one.** Consumers subscribe to
  a signal by name instead of discovering a receiver entity; that is the
  non-standard part, and it is confined to this one seam.
  [hass-proflame](https://github.com/Aetf/hass-proflame) is the first
  consumer.
- **The payload is the shape the upstream sketch describes** — frequency, raw
  timings, RSSI, timestamp — so when a real receiver platform lands, this
  integration grows a receiver entity and consumers migrate with little
  churn.

Roadmap, in order:

1. Replace the dispatcher bridge with a receiver entity the moment an
   upstream receiver platform exists, and deprecate the signal.
2. Track daemon-side authentication when it lands (a wire-protocol major
   bump); the config flow already refuses protocol versions it does not
   speak.
3. Aim the transmitter at Home Assistant core once the receiver story is
   standard and the wire protocol has been stable across releases.

[architecture #1365]: https://github.com/home-assistant/architecture/discussions/1365

## License

MIT OR Apache-2.0, at your option.

# HackRF Proxy for Home Assistant

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

Via [HACS](https://hacs.xyz/): add `https://github.com/Aetf/hass-hackrf-proxy`
as a custom repository (category: integration), install, and restart Home
Assistant. Manual alternative: copy `custom_components/hackrf_proxy/` into
your config's `custom_components/` and restart.

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

| entity | source | during an outage |
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

**Last frame heard is the receive path's only witness.** A receiver that has
gone deaf — the radio moved, the antenna came off, the gain is wrong — looks
from every other reading exactly like a quiet room. It counts every burst the
detector sliced, not only frames a consumer recognised, so it stays honest
about the radio rather than about any one consumer.

Only `status` is polled, once a minute, and it is answered from the daemon's
own bookkeeping without touching the radio or the air.

### Receiving

Until an upstream receiver platform exists, every frame the daemon hears is
re-broadcast on the dispatcher signal `hackrf_proxy_rx_frame_{entry_id}`,
with the daemon's `rx_frame` payload verbatim. That payload is deliberately
the shape a future receiver entity would carry, so consumers migrate with
little churn. [hass-proflame](https://github.com/Aetf/hass-proflame) is the
first consumer of both paths.

## License

MIT OR Apache-2.0, at your option.

"""Constants for the HackRF Proxy integration."""

DOMAIN = "hackrf_proxy"

DEFAULT_PORT = 8765

# The daemon tunes anywhere its radio can, and a HackRF One covers 1 MHz to
# 6 GHz. Reporting the true range rather than a couple of ISM bands is what
# lets a consumer on an unusual frequency find this transmitter at all.
FREQUENCY_RANGE = (1_000_000, 6_000_000_000)

# Broadcast to consumers for every frame the daemon receives, until an upstream
# receiver platform exists. Formatted with the config entry id.
SIGNAL_RX_FRAME = f"{DOMAIN}_rx_frame_{{}}"

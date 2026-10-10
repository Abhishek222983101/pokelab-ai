"""Brain entrypoint: connect to labd, rebuild state from the event log,
then hand control to Oak's loop (P4+). Supervision (§11.2): if the
connection drops, reconnect with backoff and replay from `last_seq` —
nothing here is ever lost, because nothing is ever stored only in memory
longer than it takes to fold the next event.
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys

from pokelab_brain.bus import BrainBus
from pokelab_brain.state import StateProjection

logger = logging.getLogger(__name__)


async def run(bus_url: str, brain_secret: str, max_backoff_s: float = 30.0) -> None:
    state = StateProjection()
    backoff = 1.0
    while True:
        bus = BrainBus(bus_url, brain_secret)
        try:
            await bus.connect()
            logger.info("brain connected to labd at %s", bus_url)
            backoff = 1.0  # reset on a successful connect
            async for event in bus.subscribe(since=state.last_seq):
                state.apply(event)
                # P4 wires Oak's reaction to new events in here; for now the
                # brain just keeps an accurate, crash-safe projection.
        except (ConnectionError, OSError) as e:
            logger.warning("brain lost connection to labd (%s) — retrying in %.1fs", e, backoff)
        finally:
            await bus.close()
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, max_backoff_s)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    host = os.environ.get("LABD_HOST", "127.0.0.1")
    port = os.environ.get("LABD_PORT", "7700")
    secret = os.environ.get("LABD_BRAIN_SECRET")
    if not secret:
        print("LABD_BRAIN_SECRET not set — refusing to start without it", file=sys.stderr)
        sys.exit(1)
    bus_url = f"ws://{host}:{port}/internal/brain"
    asyncio.run(run(bus_url, secret))


if __name__ == "__main__":
    main()

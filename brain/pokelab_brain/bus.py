"""The brain's connection to labd (§5.4.3): a single trusted WebSocket to
`/internal/brain`, authenticated with LABD_BRAIN_SECRET. Everything the
brain decides becomes a `publish` call here — there is no other path for
brain state to reach the event log, the same discipline the Rust side
enforces for its own writes (lab-gateway's Hub).

One WebSocket, ONE reader: `recv()` on the same connection from two
coroutines at once raises (websockets' own `ConcurrencyError`), and this
protocol genuinely needs to do two things on one socket at once —
subscribe to the live event stream AND wait for a specific command's
reply. So a single background task owns `recv()` and demultiplexes by
`req` (command replies) or `type == "event"` (the subscription queue).
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncIterator

import websockets

logger = logging.getLogger(__name__)


@dataclass
class Event:
    seq: int
    ts: str
    kind: str
    v: int
    project: str | None
    actor: str
    corr: str | None
    causation: int | None
    payload: dict[str, Any]
    display: dict[str, Any] | None = None


class BrainBus:
    def __init__(self, url: str, brain_secret: str):
        self.url = url
        self.brain_secret = brain_secret
        self._ws: websockets.ClientConnection | None = None
        self._reader_task: asyncio.Task | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._event_queue: asyncio.Queue[Event] = asyncio.Queue()

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            self.url,
            additional_headers={"Authorization": f"Bearer {self.brain_secret}"},
        )
        self._reader_task = asyncio.create_task(self._read_loop())

    async def close(self) -> None:
        if self._reader_task is not None:
            self._reader_task.cancel()
            try:
                await self._reader_task
            except (asyncio.CancelledError, Exception):
                pass
            self._reader_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def _read_loop(self) -> None:
        assert self._ws is not None
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                msg_type = msg.get("type")
                if msg_type == "event":
                    e = msg["e"]
                    await self._event_queue.put(
                        Event(
                            seq=e["seq"], ts=e["ts"], kind=e["kind"], v=e["v"],
                            project=e.get("project"), actor=e["actor"], corr=e.get("corr"),
                            causation=e.get("causation"), payload=e["payload"], display=e.get("display"),
                        )
                    )
                elif msg_type in ("published", "job_accepted", "job_rejected"):
                    req = msg.get("req")
                    fut = self._pending.pop(req, None)
                    if fut is not None and not fut.done():
                        fut.set_result(msg)
                    else:
                        logger.debug("bus: reply for unknown/already-resolved req=%s: %s", req, msg_type)
                else:
                    logger.debug("bus: unhandled message type %r", msg_type)
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # wake up anyone still waiting on a reply — the connection is gone
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("labd connection closed"))
            self._pending.clear()

    async def _send_and_wait(self, payload: dict[str, Any], req: str) -> dict[str, Any]:
        assert self._ws is not None, "call connect() first"
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req] = fut
        await self._ws.send(json.dumps(payload))
        return await fut

    async def publish(self, events: list[dict[str, Any]], req: str) -> list[int]:
        reply = await self._send_and_wait({"type": "publish", "events": events, "req": req}, req)
        return reply["seqs"]

    async def job_submit(
        self, kit: str, config: dict[str, Any], req: str, project: str | None = None
    ) -> str:
        reply = await self._send_and_wait(
            {"type": "job_submit", "req": req, "kit": kit, "config": config, "project": project}, req
        )
        if reply.get("type") == "job_rejected":
            raise RuntimeError(f"labd rejected job_submit: {reply.get('reason')}")
        return reply["job_id"]

    async def subscribe_once(self) -> None:
        """Sends `subscribe`; events (replay + live) arrive via the normal
        reader loop into the event queue that `events()` drains."""
        assert self._ws is not None, "call connect() first"
        await self._ws.send(json.dumps({"type": "subscribe", "since": 0}))

    async def subscribe(self, since: int = 0) -> AsyncIterator[Event]:
        """Sends `subscribe` and yields every event from here on (replay of
        `since` plus live). Safe to run concurrently with `publish`/
        `job_submit` on the same connection — see the module docstring."""
        assert self._ws is not None, "call connect() first"
        await self._ws.send(json.dumps({"type": "subscribe", "since": since}))
        while True:
            yield await self._event_queue.get()

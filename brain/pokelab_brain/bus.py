"""The brain's connection to labd (§5.4.3): a single trusted WebSocket to
`/internal/brain`, authenticated with LABD_BRAIN_SECRET. Everything the
brain decides becomes a `publish` call here — there is no other path for
brain state to reach the event log, the same discipline the Rust side
enforces for its own writes (lab-gateway's Hub).
"""
from __future__ import annotations

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
    """One connection, one in-flight command at a time per `req` id — the
    caller is responsible for matching replies to requests (we hand back
    whatever labd sends, tagged by `type`)."""

    def __init__(self, url: str, brain_secret: str):
        self.url = url
        self.brain_secret = brain_secret
        self._ws: websockets.ClientConnection | None = None

    async def connect(self) -> None:
        self._ws = await websockets.connect(
            self.url,
            additional_headers={"Authorization": f"Bearer {self.brain_secret}"},
        )

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
            self._ws = None

    async def publish(self, events: list[dict[str, Any]], req: str) -> list[int]:
        """Returns the committed seq for each event, in order."""
        assert self._ws is not None, "call connect() first"
        await self._ws.send(json.dumps({"type": "publish", "events": events, "req": req}))
        async for raw in self._ws:
            msg = json.loads(raw)
            if msg.get("type") == "published" and msg.get("req") == req:
                return msg["seqs"]
            logger.debug("bus: ignoring message while waiting for publish reply: %s", msg.get("type"))
        raise ConnectionError("labd closed the connection before replying to publish")

    async def job_submit(
        self, kit: str, config: dict[str, Any], req: str, project: str | None = None
    ) -> str:
        """Returns the job_id, or raises if labd rejects the submission
        (e.g. no warm pool configured)."""
        assert self._ws is not None, "call connect() first"
        await self._ws.send(
            json.dumps({"type": "job_submit", "req": req, "kit": kit, "config": config, "project": project})
        )
        async for raw in self._ws:
            msg = json.loads(raw)
            if msg.get("req") != req:
                continue
            if msg.get("type") == "job_accepted":
                return msg["job_id"]
            if msg.get("type") == "job_rejected":
                raise RuntimeError(f"labd rejected job_submit: {msg.get('reason')}")
        raise ConnectionError("labd closed the connection before replying to job_submit")

    async def subscribe(self, since: int = 0) -> AsyncIterator[Event]:
        """Subscribes and yields every `event` message labd sends from
        here on (including the replay of anything since `since`)."""
        assert self._ws is not None, "call connect() first"
        await self._ws.send(json.dumps({"type": "subscribe", "since": since}))
        async for raw in self._ws:
            msg = json.loads(raw)
            if msg.get("type") == "event":
                e = msg["e"]
                yield Event(
                    seq=e["seq"], ts=e["ts"], kind=e["kind"], v=e["v"],
                    project=e.get("project"), actor=e["actor"], corr=e.get("corr"),
                    causation=e.get("causation"), payload=e["payload"], display=e.get("display"),
                )

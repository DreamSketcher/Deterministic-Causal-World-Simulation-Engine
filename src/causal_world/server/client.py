"""Blocking WebSocket client for one life session (tests + `causal-world play`).

Deliberately thin: one request → one primary response; unsolicited messages
(``finished``) are queued and read out via ``poll``/``next_event`` so a
strict request/response test never mistakes an event for a reply.
"""

from __future__ import annotations

import json


class LifeClient:
    def __init__(self, url: str, timeout: float = 30.0) -> None:
        from websockets.sync.client import connect

        self.ws = connect(url, open_timeout=timeout)
        self.timeout = timeout
        self._pending: list[dict] = []

    # ---------------------------------------------------------- plumbing --
    def _request(self, obj: dict, *expected: str) -> dict:
        self.ws.send(json.dumps(obj))
        while True:
            if self._pending:
                msg = self._pending.pop(0)
            else:
                msg = json.loads(self.ws.recv(timeout=self.timeout))
            if msg.get("type") in expected:
                return msg
            self._pending.append(msg)  # event for the app, not this reply

    def next_event(self, timeout: float | None = None) -> dict | None:
        """Pop a queued (or freshly arriving) message — e.g. `finished`."""
        if self._pending:
            return self._pending.pop(0)
        try:
            raw = self.ws.recv(timeout=timeout if timeout is not None else 0.5)
        except TimeoutError:
            return None
        return json.loads(raw)

    # ------------------------------------------------------------ actions --
    def hello_new(self, **cfg) -> dict:
        return self._request({"type": "hello", **cfg}, "welcome", "error")

    def hello_resume(self, session_id: str) -> dict:
        return self._request({"type": "hello", "session": session_id},
                             "welcome", "error")

    def decide(self, seq: int, action: int) -> dict:
        return self._request({"type": "decide", "seq": seq, "action": action},
                             "frame", "error")

    def bio(self, md: bool = False, agent: str | None = None) -> dict:
        msg: dict = {"type": "bio", "md": md}
        if agent:
            msg["agent"] = agent
        return self._request(msg, "biography", "error")

    def autopsy(self) -> dict:
        return self._request({"type": "autopsy"}, "autopsy", "error")

    def close(self) -> dict:
        return self._request({"type": "close"}, "closed", "error")

    def send_raw(self, data) -> None:
        self.ws.send(data if isinstance(data, (str, bytes)) else str(data))

    def recv_raw(self, timeout: float = 5.0) -> dict:
        return json.loads(self.ws.recv(timeout=timeout))

    def terminate(self) -> None:
        try:
            self.ws.close()
        except Exception:
            pass

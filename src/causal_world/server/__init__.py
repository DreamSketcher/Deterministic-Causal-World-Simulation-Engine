"""v0.6 step 5: the network game layer (session state machine + WS transport).

Kernel untouched; the engine does not import this package. Session is
transport-free (thread-safe, directly testable); ws.py is thin glue and the
only module that may import `websockets`.
"""

from causal_world.server.session import ProtocolError, Session

__all__ = ["ProtocolError", "Session", "serve"]


def __getattr__(name):  # lazy: websockets is an optional extra
    if name == "serve":
        from causal_world.server.ws import serve

        return serve
    raise AttributeError(name)

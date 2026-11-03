"""Releasing the amplifier's serial connection."""

from __future__ import annotations


def close_client(client) -> None:
    """Close a pymonoprice connection now instead of when it is garbage-collected.

    serialx opens the port exclusively and `pymonoprice` has no close(), so the port
    stays held until the Python object happens to be destroyed. A reload needs it
    free right away, and the private port is the only handle.
    Does nothing for a client without one.
    """
    port = getattr(client, "_port", None)
    close = getattr(port, "close", None)
    if callable(close):
        close()

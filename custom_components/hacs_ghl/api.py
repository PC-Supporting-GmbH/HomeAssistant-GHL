"""GHL API client."""

from __future__ import annotations

import asyncio


class GHLAPIError(Exception):
    """Base exception for GHL API errors."""


class GHLConnectionError(GHLAPIError):
    """Error communicating with the GHL device."""


class GHLAPI:
    """Client for the GHL TCP API."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize the GHL API client."""

        self.host = host
        self.port = port

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    async def _async_connect(self) -> None:
        """Open the TCP connection to the GHL device."""

        if (
            self._reader is not None
            and self._writer is not None
            and not self._writer.is_closing()
        ):
            return

        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=10,
            )

        except (OSError, asyncio.TimeoutError) as err:
            self._reader = None
            self._writer = None

            raise GHLConnectionError(
                f"Unable to connect to {self.host}:{self.port}"
            ) from err

    async def _async_disconnect(self) -> None:
        """Close the TCP connection to the GHL device."""

        writer = self._writer

        self._reader = None
        self._writer = None

        if writer is None:
            return

        try:
            writer.close()
            await writer.wait_closed()

        except (OSError, ConnectionResetError):
            pass

    async def async_close(self) -> None:
        """Close the GHL API client."""

        async with self._lock:
            await self._async_disconnect()

    async def async_command(self, command: str) -> str:
        """Send a command to the GHL device and return its reply."""

        async with self._lock:
            for attempt in range(2):
                try:
                    await self._async_connect()

                    if self._reader is None or self._writer is None:
                        raise GHLConnectionError(
                            f"Unable to connect to {self.host}:{self.port}"
                        )

                    self._writer.write((command + "\n").encode())
                    await self._writer.drain()

                    reply = await asyncio.wait_for(
                        self._reader.read(256),
                        timeout=10,
                    )

                    if not reply:
                        raise GHLConnectionError(
                            f"Connection to {self.host}:{self.port} was closed "
                            f"while executing: {command}"
                        )

                    await asyncio.sleep(0.1)

                    return reply.decode("cp1252").strip()

                except (
                    OSError,
                    asyncio.TimeoutError,
                    ConnectionResetError,
                    GHLConnectionError,
                ) as err:
                    await self._async_disconnect()

                    if attempt == 0:
                        await asyncio.sleep(3)
                        continue

                    raise GHLConnectionError(
                        f"Error communicating with {self.host}:{self.port} "
                        f"while executing: {command}"
                    ) from err

        raise GHLConnectionError(
            f"Error communicating with {self.host}:{self.port} "
            f"while executing: {command}"
        )

    async def async_get(self, resource: str, feature: str) -> str | None:
        """Read a value from the GHL API."""

        reply = await self.async_command(f"GET {resource} {feature}")

        if reply.startswith("NACK"):
            return None

        if not reply.startswith("ACK"):
            raise GHLAPIError(f"Unexpected GHL response: {reply}")

        if "<" not in reply or ">" not in reply:
            return None

        value = reply.split("<", 1)[1].rsplit(">", 1)[0]

        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]

        return value
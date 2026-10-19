"""GHL API client."""

from __future__ import annotations

import asyncio

from .const import (
    SETUP_CONNECTION_ATTEMPTS,
    SETUP_CONNECTION_RETRY_DELAY_SECONDS,
    SETUP_CONNECTION_TIMEOUT_SECONDS,
)


class GHLAPIError(Exception):
    """Base exception for GHL API errors."""


class GHLConnectionError(GHLAPIError):
    """Error communicating with the GHL device."""


class GHLCommandUncertainError(GHLAPIError):
    """A command may have been executed without confirmation."""


class GHLAPI:
    """Client for the GHL TCP API."""

    def __init__(self, host: str, port: int) -> None:
        """Initialize the GHL API client."""

        self.host = host
        self.port = port

        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()

    async def _async_connect(self, timeout: float = 10) -> None:
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
                timeout=timeout,
            )

        except (OSError, asyncio.TimeoutError) as err:
            self._reader = None
            self._writer = None

            raise GHLConnectionError(
                f"Unable to connect to {self.host}:{self.port}"
            ) from err

    async def async_check_connection(self) -> None:
        """Check the connection to the GHL device."""

        async with self._lock:
            for attempt in range(SETUP_CONNECTION_ATTEMPTS):
                try:
                    await self._async_connect(
                        timeout=SETUP_CONNECTION_TIMEOUT_SECONDS,
                    )
                    return

                except GHLConnectionError:
                    if attempt == SETUP_CONNECTION_ATTEMPTS - 1:
                        raise

                    await asyncio.sleep(
                        SETUP_CONNECTION_RETRY_DELAY_SECONDS
                    )

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

    async def async_command(
        self,
        command: str,
        *,
        retry_safe: bool = False,
    ) -> str:
        """Send a command to the GHL device and return its reply."""

        may_retry = command.startswith("GET ") or retry_safe

        async with self._lock:
            for attempt in range(2):
                command_may_have_been_sent = False

                try:
                    await self._async_connect()

                    if self._reader is None or self._writer is None:
                        raise GHLConnectionError(
                            f"Unable to connect to {self.host}:{self.port}"
                        )

                    payload = (command + "\n").encode()
                    command_may_have_been_sent = True
                    self._writer.write(payload)
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

                    response = reply.decode("cp1252").strip()

                    if (
                        not may_retry
                        and response != "ACK"
                        and not response.startswith("NACK")
                    ):
                        await self._async_disconnect()
                        raise GHLCommandUncertainError(
                            f"Execution could not be confirmed for: {command}"
                        )

                    return response

                except (
                    OSError,
                    asyncio.TimeoutError,
                    ConnectionResetError,
                    GHLConnectionError,
                ) as err:
                    await self._async_disconnect()

                    if command_may_have_been_sent and not may_retry:
                        raise GHLCommandUncertainError(
                            f"Execution could not be confirmed for: {command}"
                        ) from err

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
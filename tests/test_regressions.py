"""Regression tests using current GHL source and simulated device responses."""
from __future__ import annotations

import asyncio
import ast
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

from support import COMPONENT, load_definitions, production_namespace

NS = production_namespace()
GHLAPI = NS["GHLAPI"]
APIError = NS["GHLAPIError"]
ConnectionError = NS["GHLConnectionError"]
UncertainError = NS["GHLCommandUncertainError"]


class SimulatedReader:
    def __init__(self, replies):
        self.replies = iter(replies)

    async def read(self, size):
        reply = next(self.replies)
        if isinstance(reply, BaseException):
            raise reply
        return reply


class SimulatedWriter:
    def __init__(self):
        self.commands = []
        self.closed = 0
        self.waited = 0

    def write(self, data):
        self.commands.append(data)

    async def drain(self):
        pass

    def close(self):
        self.closed += 1

    async def wait_closed(self):
        self.waited += 1


class APITests(unittest.IsolatedAsyncioTestCase):
    def client(self, replies):
        api = GHLAPI("simulated.local", 10002)
        reader = SimulatedReader(replies)
        writer = SimulatedWriter()

        async def connect(*args, **kwargs):
            api._reader, api._writer = reader, writer

        api._async_connect = AsyncMock(side_effect=connect)
        # Avoid real delays while preserving the production retry logic.
        real_asyncio = asyncio
        NS["asyncio"] = SimpleNamespace(
            Lock=real_asyncio.Lock, wait_for=real_asyncio.wait_for,
            TimeoutError=real_asyncio.TimeoutError, sleep=AsyncMock(),
        )
        self.addCleanup(NS.__setitem__, "asyncio", real_asyncio)
        return api, writer

    async def test_read_retries_after_timeout(self):
        api, writer = self.client([asyncio.TimeoutError(), b"ACK <7.2>"])
        self.assertEqual(await api.async_command("GET SENSOR[0] ACTVALUE"), "ACK <7.2>")
        self.assertEqual(len(writer.commands), 2)

    async def test_read_fails_after_two_attempts(self):
        api, writer = self.client([asyncio.TimeoutError(), asyncio.TimeoutError()])
        with self.assertRaises(ConnectionError):
            await api.async_command("GET SENSOR[0] ACTVALUE")
        self.assertEqual(len(writer.commands), 2)

    async def test_uncertain_action_is_not_repeated(self):
        api, writer = self.client([asyncio.TimeoutError(), b"ACK"])
        with self.assertRaises(UncertainError):
            await api.async_command("SET SPECIALFUNCTION WATERCHANGE[0] 1")
        self.assertEqual(len(writer.commands), 1)

    async def test_closed_connection_after_write_is_uncertain(self):
        api, writer = self.client([b"", b"ACK"])
        with self.assertRaises(UncertainError):
            await api.async_command("SET SPECIALFUNCTION MAINTENANCE[0] 1")
        self.assertEqual(len(writer.commands), 1)

    async def test_explicitly_safe_write_can_retry(self):
        api, writer = self.client([asyncio.TimeoutError(), b"ACK"])
        self.assertEqual(await api.async_command("SET ILLUMINATION MASTERBRIGHTNESS 50", retry_safe=True), "ACK")
        self.assertEqual(len(writer.commands), 2)

    async def test_nack_is_returned_without_retry(self):
        api, writer = self.client([b"NACK (-105)"])
        self.assertEqual(await api.async_command("SET ILLUMINATION MASTERBRIGHTNESS 50"), "NACK (-105)")
        self.assertEqual(len(writer.commands), 1)

    async def test_malformed_write_reply_is_uncertain(self):
        api, writer = self.client([b"ACK <unexpected>"])
        with self.assertRaises(UncertainError):
            await api.async_command("SET SPECIALFUNCTION THUNDERSTORM 5")
        self.assertEqual(len(writer.commands), 1)

    async def test_nack_after_uncertain_safe_write_stays_uncertain(self):
        api, writer = self.client([asyncio.TimeoutError(), b"NACK (-105)"])
        with self.assertRaises(UncertainError):
            await api.async_command("SET ILLUMINATION MASTERBRIGHTNESS 50", retry_safe=True)
        self.assertEqual(len(writer.commands), 2)

    async def test_invalid_description_character_is_replaced(self):
        api, writer = self.client([b'ACK <"Bad\x81name">'])
        with self.assertLogs("ghl-regression", "WARNING"):
            self.assertEqual(await api.async_get("SENSOR[0]", "DESCRIPTION"), "Bad\ufffdname")
        self.assertEqual(len(writer.commands), 1)

    async def test_valid_description_characters_survive(self):
        api, _ = self.client(['ACK <"Süßwasser">'.encode("cp1252")])
        self.assertEqual(await api.async_get("SENSOR[0]", "DESCRIPTION"), "Süßwasser")

    async def test_invalid_numeric_encoding_is_not_cleaned(self):
        api, writer = self.client([b"ACK <2\x815>", b"ACK <25>"])
        self.assertEqual(await api.async_get("SENSOR[0]", "ACTVALUE"), "25")
        self.assertEqual(len(writer.commands), 2)

    async def test_invalid_write_encoding_never_repeats_action(self):
        api, writer = self.client([b"ACK\x81", b"ACK"])
        with self.assertRaises(UncertainError):
            await api.async_command("SET SPECIALFUNCTION THUNDERSTORM 5")
        self.assertEqual(len(writer.commands), 1)

    async def test_control_characters_never_reach_device(self):
        api, writer = self.client([])
        with self.assertRaises(APIError):
            await api.async_command("GET SENSOR[0] ACTVALUE\nSET SPECIALFUNCTION THUNDERSTORM 5")
        self.assertEqual(writer.commands, [])

    async def test_close_is_idempotent(self):
        api, writer = self.client([])
        await api._async_connect()
        await api.async_close()
        await api.async_close()
        self.assertEqual((writer.closed, writer.waited), (1, 1))
        self.assertIsNone(api._reader)
        self.assertIsNone(api._writer)

    async def test_commands_do_not_overlap(self):
        api, writer = self.client([b"ACK <1>", b"ACK <2>"])
        active = 0
        peak = 0

        async def read(size):
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            await asyncio.sleep(0)
            active -= 1
            return b"ACK <1>"

        api._async_connect.side_effect = None
        api._reader = SimpleNamespace(read=read)
        api._writer = writer
        await asyncio.gather(api.async_command("GET SENSOR[0] ACTVALUE"), api.async_command("GET SENSOR[1] ACTVALUE"))
        self.assertEqual(peak, 1)
        self.assertEqual(len(writer.commands), 2)


class ValueTests(unittest.TestCase):
    def test_pointcount_accepts_whole_counts(self):
        for value, expected in (("0", 0), ("24.000", 24), ("25", 25), ("200", 200)):
            with self.subTest(value=value):
                self.assertEqual(NS["parse_pointcount"](value), expected)

    def test_pointcount_rejects_invalid_counts(self):
        for value in ("-1", "2.5", "nan", "inf", "-inf", "abc"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                NS["parse_pointcount"](value)

    def test_description_validation(self):
        for value in ("", "Aquarium", "a" * 16, "<Test>", "Süßwasser"):
            self.assertTrue(NS["is_valid_description"](value), value)
        for value in ('Bad"name', "a" * 17, "Bad\nname", "Bad\tname"):
            self.assertFalse(NS["is_valid_description"](value), value)

    def test_device_info_preserves_empty_name_and_identity(self):
        for title in ("P4", ""):
            entry = SimpleNamespace(entry_id="stable", title=title, data={"host": "test.local"})
            info = NS["device_info"](entry)
            self.assertEqual(info, {"identifiers": {("pcs_ghl", "stable")}, "name": title, "manufacturer": "GHL", "configuration_url": "http://test.local"})

    def test_numeric_and_documented_switch_states(self):
        ns = production_namespace()
        load_definitions("coordinator.py", {"_convert_value", "_convert_switch_state"}, ns)
        for value in ("nan", "inf", "-inf", "abc"):
            with self.subTest(value=value), self.assertLogs("ghl-regression", "WARNING"):
                self.assertIsNone(ns["_convert_value"](value))
        self.assertEqual(ns["_convert_value"]("24.5"), 24.5)
        self.assertFalse(ns["_convert_switch_state"]("0.000", binary_only=True))
        self.assertTrue(ns["_convert_switch_state"]("1.000", binary_only=True))
        with self.assertLogs("ghl-regression", "WARNING"):
            self.assertIsNone(ns["_convert_switch_state"]("2", binary_only=True))
        self.assertTrue(ns["_convert_switch_state"]("2"))


class HistoryTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ns = production_namespace()
        load_definitions("history.py", {"GHLHistoryRecord", "_parse_history_record", "_parse_ack_value", "_api_resource_name", "_async_read_history", "_build_measurement_statistics"}, self.ns)
        self.resource = SimpleNamespace(resource="SENSOR", index=0)

    def api(self, replies):
        replies = iter(replies)
        return SimpleNamespace(async_command=AsyncMock(side_effect=lambda command: next(replies)))

    async def test_bad_record_is_skipped_and_next_record_imported(self):
        api = self.api(['ACK <"1700000000,1,2,3,0">', 'ACK <"bad,1,2,3,0">', 'ACK <"1700003600,4,5,6,0">', "NACK (-104)"])
        with self.assertLogs("ghl-regression", "WARNING"):
            result = await self.ns["_async_read_history"](api, self.resource)
        self.assertEqual([r.values[0] for r in result], [1.0, 4.0])
        self.assertEqual(api.async_command.call_count, 4)
        self.assertIn("DATARECORD[2]", api.async_command.call_args_list[2].args[0])

    async def test_empty_history_ends_normally(self):
        api = self.api(["NACK (-104)"])
        self.assertEqual(await self.ns["_async_read_history"](api, self.resource), [])

    async def test_other_nack_is_not_end_of_history(self):
        api = self.api(["NACK (-102)"])
        with self.assertLogs("ghl-regression", "WARNING"):
            self.assertIsNone(await self.ns["_async_read_history"](api, self.resource))

    async def test_duplicate_timestamps_are_removed(self):
        api = self.api(['ACK <"1700000000,1,2,3,0">'] * 2 + ["NACK (-104)"])
        self.assertEqual(len(await self.ns["_async_read_history"](api, self.resource)), 1)

    async def test_communication_error_propagates(self):
        api = SimpleNamespace(async_command=AsyncMock(side_effect=self.ns["GHLConnectionError"]("test")))
        with self.assertRaises(self.ns["GHLAPIError"]):
            await self.ns["_async_read_history"](api, self.resource)

    async def test_unrepresentable_timestamp_is_rejected(self):
        self.assertIsNone(self.ns["_parse_history_record"]("-99999999999999999999999999,1,2,3,0"))
        self.assertIsNotNone(self.ns["_parse_history_record"]("1700000000,1,2,3,0"))


class SetupTests(unittest.IsolatedAsyncioTestCase):
    async def test_setup_registers_cleanup_before_connection_and_discovery(self):
        # Execute the actual setup until a simulated discovery failure. The
        # harness invokes callbacks when setup fails, as HA's lifecycle does.
        ns = production_namespace()
        load_definitions("__init__.py", {"_async_setup_entry"}, ns)
        callbacks = []
        clients = []
        writer = SimulatedWriter()

        class Client(ns["GHLAPI"]):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                clients.append(self)

            async def async_check_connection(self):
                self._reader = object()
                self._writer = writer

        async def discover(**kwargs):
            self.assertIn(clients[0].async_close, callbacks)
            raise RuntimeError("simulated discovery failure")

        ns.update(GHLAPI=Client, async_discover_resources=discover, CONF_HOST="host", CONF_PORT="port", ConfigEntryNotReady=RuntimeError)
        entry = SimpleNamespace(entry_id="entry", title="P4", data={"host": "test.local", "port": 10002, "device_type": "profilux_4"}, options={}, async_on_unload=callbacks.append)
        try:
            with self.assertRaisesRegex(RuntimeError, "simulated discovery failure"):
                await ns["_async_setup_entry"](SimpleNamespace(), entry)
        finally:
            for cleanup in callbacks:
                await cleanup()
        self.assertEqual(writer.closed, 1)
        self.assertIsNone(clients[0]._writer)


class SourceChecks(unittest.TestCase):
    def test_all_production_python_files_compile(self):
        for path in COMPONENT.glob("*.py"):
            with self.subTest(file=path.name):
                compile(path.read_bytes(), str(path), "exec")

    def test_translations_are_valid_json_without_duplicate_keys(self):
        def unique_pairs(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise AssertionError(f"Duplicate JSON key: {key}")
                result[key] = value
            return result
        for path in (COMPONENT / "translations").glob("*.json"):
            with self.subTest(file=path.name):
                json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_pairs)


class ResponseTypeTests(unittest.IsolatedAsyncioTestCase):
    client = APITests.client

    async def test_numeric_ack_on_first_attempt(self):
        """ACK with a numeric value succeeds on the first attempt."""
        for raw, expected in ((b"ACK <7.200>", "7.200"), (b"ACK <0.000>", "0.000"), (b"ACK <-2.500>", "-2.500")):
            with self.subTest(reply=raw):
                api, writer = self.client([raw])
                self.assertEqual(await api.async_get("SENSOR[0]", "ACTVALUE"), expected)
                self.assertEqual(writer.commands, [b"GET SENSOR[0] ACTVALUE\n"])
                self.assertEqual(writer.closed, 0)

    async def test_quoted_text_ack_on_first_attempt(self):
        """ACK with quoted text returns the text without surrounding quotes."""
        api, writer = self.client([b'ACK <"Aquarium">'])
        self.assertEqual(await api.async_get("SENSOR[0]", "DESCRIPTION"), "Aquarium")
        self.assertEqual(len(writer.commands), 1)

    async def test_empty_quoted_description(self):
        """An empty quoted description remains an empty string."""
        api, _ = self.client([b'ACK <"">'])
        self.assertEqual(await api.async_get("SENSOR[0]", "DESCRIPTION"), "")

    async def test_ack_with_surrounding_whitespace(self):
        """Whitespace around a complete ACK is stripped."""
        api, _ = self.client([b" \r\nACK <7.200>\r\n"])
        self.assertEqual(await api.async_get("SENSOR[0]", "ACTVALUE"), "7.200")

    async def test_action_ack_on_first_attempt(self):
        """An action succeeds with a plain ACK and is sent once."""
        api, writer = self.client([b"ACK"])
        self.assertEqual(await api.async_command("SET SPECIALFUNCTION THUNDERSTORM 5"), "ACK")
        self.assertEqual(len(writer.commands), 1)
        self.assertEqual(writer.closed, 0)

    async def test_safe_write_ack_on_first_attempt(self):
        """A safe value write succeeds with ACK without a retry."""
        api, writer = self.client([b"ACK"])
        self.assertEqual(await api.async_command("SET ILLUMINATION MASTERBRIGHTNESS 50", retry_safe=True), "ACK")
        self.assertEqual(len(writer.commands), 1)

    async def test_read_nacks_return_no_value(self):
        """Documented read errors and an unknown error code return no value."""
        for code in (-1, -2, -101, -102, -103, -104, -105, -999):
            with self.subTest(code=code):
                api, writer = self.client([f"NACK ({code})".encode()])
                self.assertIsNone(await api.async_get("SENSOR[0]", "ACTVALUE"))
                self.assertEqual(len(writer.commands), 1)

    async def test_write_nacks_preserve_the_error_code(self):
        """Write rejections preserve the returned NACK for caller evaluation."""
        for code in (-101, -102, -105, -999):
            with self.subTest(code=code):
                reply = f"NACK ({code})"
                api, writer = self.client([reply.encode()])
                self.assertEqual(await api.async_command("SET ILLUMINATION MASTERBRIGHTNESS 50"), reply)
                self.assertEqual(len(writer.commands), 1)

    async def test_unexpected_read_reply_is_an_api_error(self):
        """Unrecognised or whitespace-only read replies are reported as errors."""
        for reply in (b"HELLO", b"ERROR", b"   \r\n"):
            with self.subTest(reply=reply):
                api, writer = self.client([reply])
                with self.assertRaises(APIError):
                    await api.async_get("SENSOR[0]", "ACTVALUE")
                self.assertEqual(len(writer.commands), 1)

    async def test_ack_without_complete_value_returns_none(self):
        """ACK without a complete bracket pair returns no value."""
        for reply in (b"ACK", b"ACK <7.2", b"ACK 7.2>"):
            with self.subTest(reply=reply):
                api, _ = self.client([reply])
                self.assertIsNone(await api.async_get("SENSOR[0]", "ACTVALUE"))

    async def test_empty_unquoted_ack_value(self):
        """An empty ACK value remains empty at the transport layer."""
        api, _ = self.client([b"ACK <>"])
        self.assertEqual(await api.async_get("SENSOR[0]", "ACTVALUE"), "")

    async def test_malformed_write_confirmations_are_uncertain(self):
        """An unexpected write reply never counts as successful confirmation."""
        for reply in (b"HELLO", b"ACK <1>", b"   "):
            with self.subTest(reply=reply):
                api, writer = self.client([reply])
                with self.assertRaises(UncertainError):
                    await api.async_command("SET SPECIALFUNCTION THUNDERSTORM 5")
                self.assertEqual(len(writer.commands), 1)

    async def test_read_retries_after_eof(self):
        """A closed connection on a read is reconnected and retried."""
        api, writer = self.client([b"", b"ACK <1>"])
        self.assertEqual(await api.async_get("SENSOR[0]", "ACTVALUE"), "1")
        self.assertEqual(len(writer.commands), 2)

    async def test_read_retries_after_socket_error(self):
        """A socket error on a read permits a retry."""
        api, writer = self.client([OSError("simulated"), b"ACK <1>"])
        self.assertEqual(await api.async_get("SENSOR[0]", "ACTVALUE"), "1")
        self.assertEqual(len(writer.commands), 2)

    async def test_socket_error_after_action_does_not_retry(self):
        """A socket error after an action is sent leaves execution uncertain."""
        api, writer = self.client([OSError("simulated")])
        with self.assertRaises(UncertainError):
            await api.async_command("SET SPECIALFUNCTION THUNDERSTORM 5")
        self.assertEqual(len(writer.commands), 1)

    async def test_connection_failure_before_sending_action_can_retry(self):
        """Failure before sending an action allows a connection retry."""
        api, writer = self.client([b"ACK"])
        connect = api._async_connect.side_effect
        attempts = 0

        async def fail_once():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise ConnectionError("not connected")
            await connect()

        api._async_connect.side_effect = fail_once
        self.assertEqual(await api.async_command("SET SPECIALFUNCTION THUNDERSTORM 5"), "ACK")
        self.assertEqual((attempts, len(writer.commands)), (2, 1))

    async def test_two_connection_failures_send_nothing(self):
        """Repeated connection failure is not a possibly executed action."""
        api, writer = self.client([])
        api._async_connect.side_effect = ConnectionError("not connected")
        with self.assertRaises(ConnectionError):
            await api.async_command("SET SPECIALFUNCTION THUNDERSTORM 5")
        self.assertEqual(writer.commands, [])
        self.assertEqual(api._async_connect.await_count, 2)

    async def test_repeated_bad_numeric_encoding_fails(self):
        """Repeated invalid encoding is reported instead of silently cleaned."""
        api, writer = self.client([b"ACK <2\x815>"] * 2)
        with self.assertRaises(ConnectionError):
            await api.async_get("SENSOR[0]", "ACTVALUE")
        self.assertEqual(len(writer.commands), 2)

    async def test_damaged_description_envelope_is_not_repaired(self):
        """Only a complete quoted description envelope permits replacement."""
        api, writer = self.client([b'ACK <"Bad\x81'] * 2)
        with self.assertRaises(ConnectionError):
            await api.async_get("SENSOR[0]", "DESCRIPTION")
        self.assertEqual(len(writer.commands), 2)

    async def test_cancelled_action_is_not_repeated_and_unlocks(self):
        """Cancellation does not repeat an action or leave the command lock held."""
        api, writer = self.client([asyncio.CancelledError()])
        with self.assertRaises(asyncio.CancelledError):
            await api.async_command("SET SPECIALFUNCTION THUNDERSTORM 5")
        self.assertEqual(len(writer.commands), 1)
        self.assertFalse(api._lock.locked())

    async def test_close_tolerates_socket_close_error(self):
        """Closing remains safe if waiting for socket closure raises OSError."""
        api, writer = self.client([])
        await api._async_connect()
        writer.wait_closed = AsyncMock(side_effect=OSError("already closed"))
        await api.async_close()
        self.assertIsNone(api._reader)
        self.assertIsNone(api._writer)

    async def test_close_without_connection(self):
        """Closing an unused client succeeds without connecting."""
        api, writer = self.client([])
        await api.async_close()
        api._async_connect.assert_not_awaited()
        self.assertEqual(writer.closed, 0)


class ConnectionSetupTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ns = production_namespace()
        self.open_connection = AsyncMock()
        self.ns["asyncio"] = SimpleNamespace(
            Lock=asyncio.Lock, wait_for=asyncio.wait_for, TimeoutError=asyncio.TimeoutError,
            sleep=AsyncMock(), open_connection=self.open_connection,
        )
        self.api = self.ns["GHLAPI"]("test.local", 10002)

    async def test_connect_success(self):
        """A new connection stores reader and writer returned by asyncio."""
        reader, writer = object(), SimulatedWriter()
        self.open_connection.return_value = (reader, writer)
        await self.api._async_connect()
        self.assertIs(self.api._reader, reader)
        self.assertIs(self.api._writer, writer)
        self.open_connection.assert_awaited_once_with("test.local", 10002)

    async def test_open_connection_is_reused(self):
        """An existing usable connection is not opened again."""
        self.api._reader = object()
        self.api._writer = SimpleNamespace(is_closing=lambda: False)
        await self.api._async_connect()
        self.open_connection.assert_not_awaited()

    async def test_closing_connection_is_replaced(self):
        """A connection whose writer is closing is replaced."""
        self.api._reader = object()
        self.api._writer = SimpleNamespace(is_closing=lambda: True)
        reader, writer = object(), SimulatedWriter()
        self.open_connection.return_value = (reader, writer)
        await self.api._async_connect()
        self.assertIs(self.api._writer, writer)
        self.open_connection.assert_awaited_once()

    async def test_connect_errors_are_wrapped(self):
        """Socket failures and timeouts become GHL connection errors."""
        for error in (OSError("refused"), asyncio.TimeoutError()):
            with self.subTest(error=type(error).__name__):
                self.open_connection.side_effect = error
                with self.assertRaises(self.ns["GHLConnectionError"]):
                    await self.api._async_connect()
                self.assertIsNone(self.api._reader)
                self.assertIsNone(self.api._writer)

    async def test_initial_check_succeeds_first_attempt(self):
        """Initial connection checking succeeds without another attempt."""
        self.api._async_connect = AsyncMock()
        await self.api.async_check_connection()
        self.api._async_connect.assert_awaited_once()

    async def test_initial_check_retries_until_success(self):
        """Initial setup retries a failed connection and then succeeds."""
        self.api._async_connect = AsyncMock(side_effect=[self.ns["GHLConnectionError"]("failed"), None])
        await self.api.async_check_connection()
        self.assertEqual(self.api._async_connect.await_count, 2)

    async def test_initial_check_stops_at_configured_limit(self):
        """Initial setup stops after its configured number of attempts."""
        self.api._async_connect = AsyncMock(side_effect=self.ns["GHLConnectionError"]("failed"))
        with self.assertRaises(self.ns["GHLConnectionError"]):
            await self.api.async_check_connection()
        self.assertEqual(self.api._async_connect.await_count, self.ns["SETUP_CONNECTION_ATTEMPTS"])


class DiscoveryReplyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ns = production_namespace()
        load_definitions("discovery.py", {"GHLDiscoveredResource", "_parse_ack_value", "_get_effective_maximum_index", "_async_probe_illumination_resources"}, self.ns)
        self.ns["_async_get_description"] = AsyncMock(return_value="Aquarium")
        self.ns["_async_get_feature_available"] = AsyncMock(return_value=True)

    def api(self, replies):
        replies = iter(replies)
        return SimpleNamespace(async_command=AsyncMock(side_effect=lambda cmd: next(replies)))

    async def test_normal_two_point_curve(self):
        """A normal curve reads point count and two time/brightness pairs."""
        api = self.api(["ACK <2.000>", "ACK <480>", "ACK <0>", "ACK <600>", "ACK <80>"])
        resources = await self.ns["_async_probe_illumination_resources"](api, 0)
        self.assertEqual(resources[0].data, {"point_count": 2, "curve": [{"time": 480, "brightness": 0.0}, {"time": 600, "brightness": 80.0}]})
        self.assertEqual(api.async_command.await_count, 5)

    async def test_zero_points_hidden_by_default(self):
        """A zero-point illumination channel stays hidden by default."""
        api = self.api(["ACK <0.000>"])
        self.assertEqual(await self.ns["_async_probe_illumination_resources"](api, 0), [])
        self.ns["_async_get_description"].assert_not_awaited()

    async def test_zero_points_shown_when_requested(self):
        """Show-all includes a zero-point channel with an empty curve."""
        api = self.api(["ACK <0.000>"])
        resources = await self.ns["_async_probe_illumination_resources"](api, 0, True)
        self.assertEqual(resources[0].data, {"point_count": 0, "curve": []})

    async def test_oversized_count_is_limited_to_24(self):
        """An oversized count warns and reads only indices 0 through 23."""
        api = self.api(["ACK <200>"] + ["ACK <1>"] * 48)
        with self.assertLogs("ghl-regression", "WARNING"):
            resources = await self.ns["_async_probe_illumination_resources"](api, 0)
        self.assertEqual(resources[0].data["point_count"], 24)
        self.assertEqual(len(resources[0].data["curve"]), 24)
        self.assertEqual(api.async_command.await_count, 49)
        self.assertTrue(api.async_command.call_args.args[0].endswith("BRIGHTNESS[23]"))

    async def test_fractional_and_nonfinite_counts_skip_channel(self):
        """Fractional, negative and non-finite counts skip the channel with a warning."""
        for value in ("2.5", "-1", "nan", "inf", "text"):
            with self.subTest(value=value):
                api = self.api([f"ACK <{value}>"])
                with self.assertLogs("ghl-regression", "WARNING"):
                    self.assertEqual(await self.ns["_async_probe_illumination_resources"](api, 0), [])
                self.assertEqual(api.async_command.await_count, 1)

    async def test_nack_skips_unavailable_channel(self):
        """An unavailable illumination channel is skipped on NACK."""
        api = self.api(["NACK (-101)"])
        self.assertEqual(await self.ns["_async_probe_illumination_resources"](api, 0), [])

    async def test_unexpected_count_response_warns(self):
        """An unknown response to POINTCOUNT warns and skips the channel."""
        api = self.api(["HELLO"])
        with self.assertLogs("ghl-regression", "WARNING"):
            self.assertEqual(await self.ns["_async_probe_illumination_resources"](api, 0), [])

    async def test_missing_count_value_skips_channel(self):
        """ACK without a point count does not create a curve."""
        for reply in ("ACK", "ACK <>", 'ACK <"">'):
            with self.subTest(reply=reply):
                self.assertEqual(await self.ns["_async_probe_illumination_resources"](self.api([reply]), 0), [])

    async def test_count_communication_error_warns(self):
        """Communication failure for POINTCOUNT warns and skips the channel."""
        api = SimpleNamespace(async_command=AsyncMock(side_effect=self.ns["GHLConnectionError"]("simulated")))
        with self.assertLogs("ghl-regression", "WARNING"):
            self.assertEqual(await self.ns["_async_probe_illumination_resources"](api, 0), [])

    async def test_malformed_point_does_not_hide_other_valid_points(self):
        """Discovery skips a malformed numeric point but reads the following point."""
        api = self.api(["ACK <2>", "ACK <bad>", "ACK <80>", "ACK <600>", "ACK <50>"])
        with self.assertLogs("ghl-regression", "WARNING"):
            resources = await self.ns["_async_probe_illumination_resources"](api, 0)
        self.assertEqual(resources[0].data["curve"], [{"time": 600, "brightness": 50.0}])


class HistoricalReplyTests(unittest.IsolatedAsyncioTestCase):
    setUp = HistoryTests.setUp
    api = HistoryTests.api

    async def test_normal_historical_record(self):
        """A complete historical record returns timestamp, three values and status."""
        api = self.api(['ACK <"1700000000,24.41,75.94,0,0">', "NACK (-104)"])
        records = await self.ns["_async_read_history"](api, self.resource)
        self.assertEqual(len(records), 1)
        self.assertEqual((records[0].timestamp, records[0].values, records[0].status), (1700000000, (24.41, 75.94, 0.0), 0))

    async def test_wrong_field_count_is_skipped(self):
        """DATARECORD with too few or too many fields is skipped."""
        for value in ("1700000000,1,2,0", "1700000000,1,2,3,0,extra"):
            with self.subTest(value=value):
                api = self.api([f'ACK <"{value}">', 'ACK <"1700003600,1,2,3,0">', "NACK (-104)"])
                with self.assertLogs("ghl-regression", "WARNING"):
                    records = await self.ns["_async_read_history"](api, self.resource)
                self.assertEqual(len(records), 1)

    async def test_bad_numeric_fields_are_skipped(self):
        """Invalid value or status fields do not prevent reading the next record."""
        for value in ("1700000000,bad,2,3,0", "1700000000,1,2,3,bad"):
            with self.subTest(value=value):
                api = self.api([f'ACK <"{value}">', 'ACK <"1700003600,1,2,3,0">', "NACK (-104)"])
                with self.assertLogs("ghl-regression", "WARNING"):
                    records = await self.ns["_async_read_history"](api, self.resource)
                self.assertEqual(len(records), 1)

    async def test_missing_ack_envelope_stops_source(self):
        """A missing protocol envelope stops the source instead of inventing a record."""
        for reply in ("HELLO", "ACK", 'ACK <"incomplete'):
            with self.subTest(reply=reply), self.assertLogs("ghl-regression", "WARNING"):
                self.assertIsNone(await self.ns["_async_read_history"](self.api([reply]), self.resource))

    async def test_records_are_sorted_oldest_first(self):
        """Newest-first device records are returned in chronological order."""
        api = self.api(['ACK <"1700003600,2,0,0,0">', 'ACK <"1700000000,1,0,0,0">', "NACK (-104)"])
        records = await self.ns["_async_read_history"](api, self.resource)
        self.assertEqual([r.timestamp for r in records], [1700000000, 1700003600])

    async def test_progress_advances_over_skipped_record(self):
        """Progress advances across a skipped record without repeating its index."""
        callback = AsyncMock()
        api = self.api(['ACK <"bad,1,2,3,0">', 'ACK <"1700000000,1,2,3,0">', "NACK (-104)"])
        with self.assertLogs("ghl-regression", "WARNING"):
            await self.ns["_async_read_history"](api, self.resource, callback)
        self.assertEqual([call.args[0] for call in callback.call_args_list], [1, 2])

    async def test_completed_hour_statistics(self):
        """Valid measurements produce hourly mean, minimum and maximum."""
        result = self.ns["_build_measurement_statistics"]([(1699999200, 10.0), (1699999260, 20.0)])
        self.assertEqual(len(result), 1)
        self.assertEqual((result[0]["mean"], result[0]["min"], result[0]["max"]), (15.0, 10.0, 20.0))

    async def test_future_and_missing_values_do_not_make_statistics(self):
        """Future timestamps and missing values do not become completed-hour statistics."""
        future = int(self.ns["datetime"].now(self.ns["timezone"].utc).timestamp()) + 7200
        self.assertEqual(self.ns["_build_measurement_statistics"]([(1700000000, None), (future, 10.0)]), [])

    async def test_singleton_resource_has_no_index(self):
        """KH Director history uses an unindexed resource command."""
        api = self.api(["NACK (-104)"])
        resource = SimpleNamespace(resource="KHDIRECTOR", index=None)
        self.assertEqual(await self.ns["_async_read_history"](api, resource), [])
        api.async_command.assert_awaited_once_with("GET KHDIRECTOR DATARECORD[0]")

    async def test_indexed_director_command(self):
        """ION Director history retains its resource index."""
        api = self.api(["NACK (-104)"])
        resource = SimpleNamespace(resource="IONDIRECTOR", index=2)
        await self.ns["_async_read_history"](api, resource)
        api.async_command.assert_awaited_once_with("GET IONDIRECTOR[2] DATARECORD[0]")


class HistoryImportResultTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.ns = production_namespace()
        load_definitions("history.py", {"GHLHistoryRecord", "GHLHistoryImportResult", "async_import_resource_history", "_build_measurement_statistics"}, self.ns)
        self.imported = []
        self.ns.update(
            history_resource_key=lambda resource: "SENSOR:0",
            _async_read_history=AsyncMock(return_value=[]),
            _measurement_entity_id=lambda **kwargs: "sensor.test",
            _value_index=lambda entry, resource: 0,
            _configured_measurement_unit=lambda entry, resource: "pH",
            _unit_class=lambda unit: None,
            _SENSOR_ERROR_MASK=512 | 1024,
            StatisticMeanType=SimpleNamespace(ARITHMETIC=1),
            async_import_statistics=lambda *args: self.imported.append(args),
        )
        self.hass = SimpleNamespace(config=SimpleNamespace(components={"recorder"}))
        self.resource = SimpleNamespace(resource="SENSOR", index=0)

    async def run_import(self):
        return await self.ns["async_import_resource_history"](self.hass, SimpleNamespace(), None, self.resource)

    async def test_valid_data_is_submitted_to_recorder(self):
        """Valid historical data is submitted to the simulated Recorder."""
        self.ns["_async_read_history"].return_value = [self.ns["GHLHistoryRecord"](1700000000, (7.2, 0, 0), 0)]
        result = await self.run_import()
        self.assertTrue(result.success)
        self.assertEqual((result.records_found, result.records_filtered, result.statistics_hours), (1, 0, 1))
        self.assertEqual(len(self.imported), 1)

    async def test_sensor_error_masks_are_filtered(self):
        """Historical sensor-error and communication-error flags filter measurements."""
        for status in (512, 1024, 1536):
            with self.subTest(status=status):
                self.ns["_async_read_history"].return_value = [self.ns["GHLHistoryRecord"](1700000000, (7.2, 0, 0), status)]
                result = await self.run_import()
                self.assertEqual((result.records_found, result.records_filtered, result.statistics_hours), (1, 1, 0))
        self.assertEqual(self.imported, [])

    async def test_nonfinite_history_values_are_filtered(self):
        """Historical NaN and infinite selected measurements are filtered."""
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                self.ns["_async_read_history"].return_value = [self.ns["GHLHistoryRecord"](1700000000, (value, 0, 0), 0)]
                result = await self.run_import()
                self.assertEqual((result.records_filtered, result.statistics_hours), (1, 0))
        self.assertEqual(self.imported, [])

    async def test_recorder_missing_reports_failure(self):
        """Missing Recorder prevents reading and reports an unsuccessful import."""
        self.hass.config.components = set()
        with self.assertLogs("ghl-regression", "WARNING"):
            result = await self.run_import()
        self.assertFalse(result.success)
        self.ns["_async_read_history"].assert_not_awaited()

    async def test_missing_entity_reports_failure(self):
        """An unregistered sensor prevents statistics submission."""
        self.ns["_async_read_history"].return_value = [self.ns["GHLHistoryRecord"](1700000000, (7.2, 0, 0), 0)]
        self.ns["_measurement_entity_id"] = lambda **kwargs: None
        with self.assertLogs("ghl-regression", "WARNING"):
            result = await self.run_import()
        self.assertFalse(result.success)
        self.assertEqual(self.imported, [])

    async def test_empty_history_is_successful_without_statistics(self):
        """An empty history is successful and does not write statistics."""
        result = await self.run_import()
        self.assertTrue(result.success)
        self.assertEqual((result.records_found, result.statistics_hours), (0, 0))
        self.assertEqual(self.imported, [])

    async def test_failed_history_read_reports_failure(self):
        """An unusable history response produces an unsuccessful import result."""
        self.ns["_async_read_history"].return_value = None
        result = await self.run_import()
        self.assertFalse(result.success)
        self.assertEqual(self.imported, [])

    async def test_history_connection_error_reports_failure(self):
        """A history connection error is converted to an unsuccessful import result."""
        self.ns["_async_read_history"].side_effect = self.ns["GHLConnectionError"]("simulated")
        with self.assertLogs("ghl-regression", "WARNING"):
            result = await self.run_import()
        self.assertFalse(result.success)
        self.assertEqual(self.imported, [])


class SetupRestartTests(unittest.IsolatedAsyncioTestCase):
    """Check deliberate setup cancellation without cancelling HA's setup task."""

    def make_case(self, worker=None):
        from copy import deepcopy
        from unittest.mock import Mock
        ns = production_namespace()
        ns.update(deepcopy=deepcopy, CONF_HOST="host", CONF_PORT="port")
        load_definitions("__init__.py", {"async_setup_entry"}, ns)
        started, release = asyncio.Event(), asyncio.Event()
        events, tasks, reloads = [], [], []
        entry = SimpleNamespace(
            entry_id="test-entry", title="Example device",
            data={"host": "old.example", "port": 10002, "access_mode": "full_access"},
            options={}, update_listeners=[],
        )
        def add_listener(callback):
            entry.update_listeners.append(callback)
            def remove():
                entry.update_listeners.remove(callback)
            return remove
        entry.add_update_listener = add_listener
        async def default_worker(hass, entry):
            started.set()
            try:
                await release.wait()
                return True
            finally:
                events.append("worker finished")
        ns["_async_setup_entry"] = worker or default_worker
        def create_task(coro, name):
            task = asyncio.create_task(coro, name=name)
            tasks.append(task)
            return task
        def reload(entry_id):
            reloads.append((entry_id, dict(entry.data)))
            events.append("reload")
        hass = SimpleNamespace(
            data={}, async_create_task=create_task,
            config_entries=SimpleNamespace(async_schedule_reload=reload),
        )
        async def cleanup(hass, entry):
            events.append("cleanup")
            hass.data.pop("pcs_ghl", None)
            return True
        ns["async_unload_entry"] = AsyncMock(side_effect=cleanup)
        task = asyncio.create_task(ns["async_setup_entry"](hass, entry))
        tasks.append(task)
        async def finish():
            for pending in tasks:
                if not pending.done():
                    pending.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self.addAsyncCleanup(finish)
        return SimpleNamespace(ns=ns, hass=hass, entry=entry, started=started,
                               release=release, events=events, tasks=tasks,
                               reloads=reloads, task=task)

    async def notify(self, case):
        for listener in list(case.entry.update_listeners):
            await listener(case.hass, case.entry)

    async def test_success_removes_temporary_listener(self):
        c = self.make_case()
        await c.started.wait()
        c.release.set()
        self.assertTrue(await c.task)
        self.assertEqual(c.entry.update_listeners, [])
        self.assertEqual(c.reloads, [])

    async def test_host_change_cancels_only_worker_then_schedules_reload(self):
        c = self.make_case()
        await c.started.wait()
        c.entry.data["host"] = "new.example"
        await self.notify(c)
        self.assertFalse(await c.task)
        self.assertEqual(c.events, ["worker finished", "reload"])
        self.assertEqual(c.reloads[0][1]["host"], "new.example")
        self.assertFalse(c.task.cancelled())
        self.assertTrue(c.tasks[1].cancelled())
        self.assertEqual(c.entry.update_listeners, [])

    async def test_port_change_cancels_worker(self):
        c = self.make_case()
        await c.started.wait()
        c.entry.data["port"] = 10003
        await self.notify(c)
        self.assertFalse(await c.task)
        self.assertEqual(c.reloads[0][1]["port"], 10003)

    async def test_unchanged_address_does_not_cancel_or_reload(self):
        c = self.make_case()
        await c.started.wait()
        await self.notify(c)
        self.assertFalse(c.tasks[1].done())
        self.assertEqual(c.reloads, [])
        c.release.set()
        self.assertTrue(await c.task)

    async def test_device_name_change_preserves_running_setup(self):
        c = self.make_case()
        await c.started.wait()
        c.entry.title = "Renamed example"
        await self.notify(c)
        self.assertFalse(c.tasks[1].done())
        self.assertEqual(c.reloads, [])
        c.release.set()
        self.assertTrue(await c.task)
        self.assertEqual(len(c.reloads), 1)

    async def test_option_change_preserves_running_setup(self):
        c = self.make_case()
        await c.started.wait()
        c.entry.options = {"show_all_resources": True}
        await self.notify(c)
        self.assertFalse(c.tasks[1].done())
        self.assertEqual(c.reloads, [])
        c.release.set()
        self.assertTrue(await c.task)
        self.assertEqual(len(c.reloads), 1)

    async def test_access_mode_change_does_not_cancel_worker(self):
        c = self.make_case()
        await c.started.wait()
        c.entry.data["access_mode"] = "read_only"
        await self.notify(c)
        self.assertFalse(c.tasks[1].done())
        self.assertEqual(c.reloads, [])
        c.release.set()
        self.assertTrue(await c.task)
        self.assertEqual(len(c.reloads), 1)

    async def test_internal_history_data_does_not_reload(self):
        c = self.make_case()
        await c.started.wait()
        c.entry.data["history_present_resources"] = ["sensor:0"]
        await self.notify(c)
        self.assertEqual(c.reloads, [])
        c.release.set()
        self.assertTrue(await c.task)

    async def test_managed_history_options_do_not_reload(self):
        c = self.make_case()
        await c.started.wait()
        options = {"import_historical_data": True}
        c.hass.data["pcs_ghl"] = {c.entry.entry_id: {"history_flow_options": options}}
        c.entry.options = options
        await self.notify(c)
        self.assertEqual(c.reloads, [])
        c.release.set()
        self.assertTrue(await c.task)

    async def test_partial_setup_is_unloaded_before_reload(self):
        c = self.make_case()
        await c.started.wait()
        c.hass.data["pcs_ghl"] = {c.entry.entry_id: {"api": object()}}
        c.entry.data["host"] = "new.example"
        await self.notify(c)
        self.assertFalse(await c.task)
        self.assertEqual(c.events, ["worker finished", "cleanup", "reload"])
        self.assertNotIn("pcs_ghl", c.hass.data)

    async def test_real_unload_closes_api_before_reload(self):
        c = self.make_case()
        await c.started.wait()
        load_definitions("__init__.py", {"async_unload_entry"}, c.ns)
        async def unload_platforms(*args):
            c.events.append("platforms unloaded")
            return True
        async def close():
            c.events.append("connection closed")
        c.hass.config_entries.async_unload_platforms = AsyncMock(side_effect=unload_platforms)
        c.entry.options = {"show_all_resources": True}
        c.hass.data["pcs_ghl"] = {c.entry.entry_id: {"api": SimpleNamespace(async_close=AsyncMock(side_effect=close))}}
        c.entry.data["host"] = "new.example"
        await self.notify(c)
        self.assertFalse(await c.task)
        self.assertEqual(c.events, ["worker finished", "platforms unloaded", "connection closed", "reload"])

    async def test_reload_waits_for_partial_cleanup(self):
        c = self.make_case()
        await c.started.wait()
        c.hass.data["pcs_ghl"] = {c.entry.entry_id: {}}
        cleaning, finish_cleanup = asyncio.Event(), asyncio.Event()
        async def cleanup(hass, entry):
            cleaning.set()
            await finish_cleanup.wait()
            return True
        c.ns["async_unload_entry"].side_effect = cleanup
        c.entry.data["host"] = "new.example"
        await self.notify(c)
        await cleaning.wait()
        self.assertEqual(c.reloads, [])
        self.assertFalse(c.task.done())
        finish_cleanup.set()
        self.assertFalse(await c.task)
        self.assertEqual(len(c.reloads), 1)

    async def test_failed_cleanup_does_not_start_new_setup(self):
        c = self.make_case()
        await c.started.wait()
        c.hass.data["pcs_ghl"] = {c.entry.entry_id: {}}
        c.ns["async_unload_entry"].return_value = False
        c.ns["async_unload_entry"].side_effect = None
        c.entry.data["host"] = "new.example"
        await self.notify(c)
        with self.assertLogs("ghl-regression", "ERROR"):
            self.assertFalse(await c.task)
        self.assertEqual(c.reloads, [])

    async def test_rapid_host_changes_schedule_one_reload_with_latest_data(self):
        c = self.make_case()
        await c.started.wait()
        for host in ["first.example", "second.example", "third.example"]:
            c.entry.data["host"] = host
            await self.notify(c)
        self.assertFalse(await c.task)
        self.assertEqual(len(c.reloads), 1)
        self.assertEqual(c.reloads[0][1]["host"], "third.example")

    async def test_pending_reload_request_is_not_duplicated(self):
        c = self.make_case()
        await c.started.wait()
        c.entry.title = "Renamed example"
        await self.notify(c)
        c.entry.data["host"] = "new.example"
        await self.notify(c)
        self.assertFalse(await c.task)
        self.assertEqual(len(c.reloads), 1)

    async def test_original_setup_failure_is_propagated(self):
        async def failure(hass, entry):
            raise RuntimeError("simulated setup failure")
        c = self.make_case(failure)
        with self.assertRaisesRegex(RuntimeError, "simulated setup failure"):
            await c.task
        self.assertEqual(c.entry.update_listeners, [])
        self.assertEqual(c.reloads, [])

    async def test_external_cancellation_is_propagated(self):
        c = self.make_case()
        await c.started.wait()
        c.task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await c.task
        self.assertEqual(c.reloads, [])
        self.assertEqual(c.entry.update_listeners, [])

    async def test_shutdown_wins_over_address_change(self):
        c = self.make_case()
        await c.started.wait()
        c.entry.data["host"] = "new.example"
        await self.notify(c)
        c.task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await c.task
        self.assertEqual(c.reloads, [])

    async def test_other_entry_setup_is_not_cancelled(self):
        first, second = self.make_case(), self.make_case()
        await first.started.wait()
        await second.started.wait()
        first.entry.data["host"] = "new.example"
        await self.notify(first)
        self.assertFalse(await first.task)
        self.assertFalse(second.tasks[1].done())
        second.release.set()
        self.assertTrue(await second.task)
        self.assertEqual(second.reloads, [])

    async def test_failed_cleanup_overrides_an_earlier_reload_request(self):
        c = self.make_case()
        await c.started.wait()
        c.entry.title = "Renamed example"
        await self.notify(c)
        c.hass.data["pcs_ghl"] = {c.entry.entry_id: {}}
        c.ns["async_unload_entry"].side_effect = None
        c.ns["async_unload_entry"].return_value = False
        c.entry.data["host"] = "new.example"
        await self.notify(c)
        with self.assertLogs("ghl-regression", "ERROR"):
            self.assertFalse(await c.task)
        self.assertEqual(c.reloads, [])

    async def test_pending_option_reload_survives_setup_failure(self):
        release, started = asyncio.Event(), asyncio.Event()
        async def worker(hass, entry):
            started.set()
            await release.wait()
            raise RuntimeError("simulated setup failure")
        c = self.make_case(worker)
        await started.wait()
        c.entry.options = {"show_all_resources": True}
        await self.notify(c)
        release.set()
        with self.assertRaisesRegex(RuntimeError, "simulated setup failure"):
            await c.task
        self.assertEqual(len(c.reloads), 1)

    async def test_actual_setup_discovery_is_cancelled_and_registered_api_closes(self):
        c = self.make_case()
        load_definitions("__init__.py", {"_async_setup_entry"}, c.ns)
        callbacks, clients = [], []
        c.entry.async_on_unload = callbacks.append
        writer = SimulatedWriter()
        base = c.ns["GHLAPI"]
        class Client(base):
            def __init__(self, **kwargs):
                super().__init__(**kwargs)
                self._reader, self._writer = object(), writer
                clients.append(self)
            async def async_check_connection(self):
                pass
        discovering = asyncio.Event()
        async def discover(**kwargs):
            discovering.set()
            await asyncio.Future()
        c.ns.update(GHLAPI=Client, async_discover_resources=discover, ConfigEntryNotReady=RuntimeError)
        c.entry.data["device_type"] = "profilux_4"
        await discovering.wait()
        self.assertEqual(clients[0].host, "old.example")
        c.entry.data["host"] = "new.example"
        await self.notify(c)
        self.assertFalse(await c.task)
        # HA runs these callbacks after a false setup result and before releasing
        # its setup lock, which allows the requested reload to start.
        for cleanup in callbacks:
            await cleanup()
        self.assertEqual(writer.closed, 1)
        self.assertIsNone(clients[0]._reader)
        self.assertIsNone(clients[0]._writer)
        self.assertEqual(len(c.reloads), 1)

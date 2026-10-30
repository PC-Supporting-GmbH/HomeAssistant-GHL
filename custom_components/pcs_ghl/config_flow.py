"""Config flow for the GHL integration."""
# pyright: reportMissingImports=false

from __future__ import annotations

import asyncio
import logging
from time import monotonic

import voluptuous as vol

from homeassistant import config_entries 
from homeassistant.config_entries import ConfigFlowResult, FlowType
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResultType, UnknownFlow
from homeassistant.helpers import device_registry as dr, selector
from homeassistant.helpers.translation import async_get_translations

from .const import (
    ACCESS_MODE_FULL_ACCESS,
    ACCESS_MODE_READ_ONLY,
    CONF_ACCESS_MODE,
    CONF_DEVICE_TYPE,
    CONF_HISTORY_PRESENT_RESOURCES,
    CONF_IMPORT_HISTORICAL_DATA,
    CONF_SENSOR_TYPE,
    CONF_SENSOR_TYPES,
    CONF_SENSOR_UNIT,
    CONF_SENSOR_UNITS,
    CONF_SHOW_ALL_RESOURCES,
    DEFAULT_PORT,
    DEVICE_TYPE_MITRAS_LX7,
    DEVICE_TYPE_MITRAS_LX8,
    DEVICE_TYPE_PROFILUX_4,
    DOMAIN,
    SENSOR_TYPE_AIR_TEMPERATURE,
    SENSOR_TYPE_CONDUCTIVITY_FRESHWATER,
    SENSOR_TYPE_CONDUCTIVITY_SEAWATER,
    SENSOR_TYPE_HIDDEN,
    SENSOR_TYPE_HUMIDITY,
    SENSOR_TYPE_OXYGEN,
    SENSOR_TYPE_PH,
    SENSOR_TYPE_REDOX,
    SENSOR_TYPE_TEMPERATURE,
    SENSOR_TYPE_UNKNOWN,
    SENSOR_TYPE_VOLTAGE,
    SENSOR_UNIT_KG_L,
    SENSOR_UNIT_MS,
    SENSOR_UNIT_PSU,
    API_COMMAND_TIMEOUT_SECONDS,
    API_REPLY_BUFFER_SIZE,
    CONF_INITIAL_HISTORY_PENDING,
    DESCRIPTION_RESOURCE_FALLBACKS,
    DESCRIPTION_RESOURCE_TRANSLATION_KEYS,
)
from .history import (
    history_resource_key,
    async_import_resource_history,
    history_resource_map,
    sensor_history_is_configured,
    sensor_history_should_import,
)


_LOGGER = logging.getLogger(__name__)


async def async_test_connection(host: str, port: int) -> str:
    """Test the connection to the GHL API."""

    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port),
        timeout=API_COMMAND_TIMEOUT_SECONDS,
    )

    try:
        writer.write(b"GET ILLUMINATION MASTERBRIGHTNESS\n")
        await writer.drain()

        reply = await asyncio.wait_for(
            reader.read(API_REPLY_BUFFER_SIZE),
            timeout=API_COMMAND_TIMEOUT_SECONDS,
        )

        return reply.decode().strip()

    finally:
        writer.close()
        await writer.wait_closed()


class GHLConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for GHL."""

    VERSION = 2

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GHLOptionsFlow:
        """Create the GHL options flow."""

        return GHLOptionsFlow()

    async def async_on_create_entry(
        self,
        result: ConfigFlowResult,
    ) -> ConfigFlowResult:
        """Start the options flow after the config entry was created."""

        config_entry = result["result"]

        options_result = await self.hass.config_entries.options.async_init(
            config_entry.entry_id,
        )

        if options_result["type"] in (FlowResultType.CREATE_ENTRY, FlowResultType.ABORT):
            return result

        result["next_flow"] = (
            FlowType.OPTIONS_FLOW,
            options_result["flow_id"],
        )

        return result

    async def async_step_user(self, user_input=None):
        """Handle the initial configuration step."""

        errors = {}

        if user_input is not None:
            if not user_input["api_enabled"]:
                errors["api_enabled"] = "api_not_enabled"

            else:
                host = user_input[CONF_HOST]
                port = user_input[CONF_PORT]

                self._async_abort_entries_match(
                    {
                        CONF_HOST: host,
                        CONF_PORT: port,
                    }
                )

                try:
                    reply = await async_test_connection(host, port)

                except (OSError, asyncio.TimeoutError):
                    errors["base"] = "cannot_connect"

                else:
                    if reply == "NACK (-105)":
                        errors["base"] = "api_not_enabled"

                    elif not reply.startswith("ACK"):
                        errors["base"] = "invalid_response"

                    else:
                        data = {
                            CONF_HOST: user_input[CONF_HOST],
                            CONF_PORT: user_input[CONF_PORT],
                            CONF_ACCESS_MODE: user_input[CONF_ACCESS_MODE],
                            CONF_DEVICE_TYPE: user_input[CONF_DEVICE_TYPE],
                            CONF_INITIAL_HISTORY_PENDING: True,
                        }

                        translations = await async_get_translations(
                            self.hass,
                            self.hass.config.language,
                            "selector",
                            {DOMAIN},
                        )

                        translation_key = (
                            f"component.{DOMAIN}.selector.device_type.options."
                            f"{user_input[CONF_DEVICE_TYPE]}"
                        )

                        device_type_name = translations.get(
                            translation_key,
                            user_input[CONF_DEVICE_TYPE],
                        )

                        return self.async_create_entry(
                            title=f"{device_type_name} ({user_input[CONF_HOST]})",
                            data=data,
                            options={
                                CONF_IMPORT_HISTORICAL_DATA: user_input[
                                    CONF_IMPORT_HISTORICAL_DATA
                                ],
                            },
                        )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(
                    CONF_DEVICE_TYPE,
                    default=DEVICE_TYPE_PROFILUX_4,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            DEVICE_TYPE_PROFILUX_4,
                            DEVICE_TYPE_MITRAS_LX7,
                            DEVICE_TYPE_MITRAS_LX8,
                        ],
                        translation_key="device_type",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_ACCESS_MODE,
                    default=ACCESS_MODE_FULL_ACCESS,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            ACCESS_MODE_READ_ONLY,
                            ACCESS_MODE_FULL_ACCESS,
                        ],
                        translation_key="access_mode",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_IMPORT_HISTORICAL_DATA,
                    default=True,
                ): bool,
                vol.Required("api_enabled", default=False): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )


class GHLOptionsFlow(config_entries.OptionsFlow):
    """Handle GHL options."""

    def __init__(self) -> None:
        """Initialize the GHL options flow."""

        self._sensors = []
        self._sensor_index = 0
        self._single_sensor = False
        self._sensor_types = {}
        self._sensor_units = {}
        self._show_all_resources = False
        self._import_historical_data = False
        self._history_task = None
        self._history_worker = None
        self._history_owner = None
        self._history_observers = set()
        self._history_registry = None
        self._history_refresh_received = asyncio.Event()
        self._history_refresh_received.set()
        self._history_dialog_closed = False
        self._history_initial = False
        self._history_source_name = None
        self._history_source_number = 0
        self._history_source_total = 0
        self._history_records = 0
        self._history_last_update = 0.0
        self._history_summary = ""
        self._history_import_failed = False
        self._history_abort_reason = None
        self._history_background_hint = ""

    async def async_step_init(self, user_input=None):
        """Initialize GHL options."""

        active_import = self.hass.data.get(f"{DOMAIN}_history_imports", {}).get(
            self.config_entry.entry_id
        )
        if (
            active_import is not None
            and active_import._history_worker is not None
            and not active_import._history_worker.done()
        ):
            self._history_owner = active_import
            self._history_initial = active_import._history_initial
            self._history_background_hint = active_import._history_background_hint
            return await self.async_step_history_import_progress()

        entry_data = (
            self.hass.data
            .get(DOMAIN, {})
            .get(self.config_entry.entry_id)
        )

        self._sensors = [
            resource
            for resource in (
                entry_data["resources"]
                if entry_data is not None
                else []
            )
            if (
                resource.resource == "SENSOR"
                and resource.index is not None
            )
        ]

        self._sensor_types = dict(
            self.config_entry.options.get(
                CONF_SENSOR_TYPES,
                {},
            )
        )

        self._sensor_units = dict(
            self.config_entry.options.get(
                CONF_SENSOR_UNITS,
                {},
            )
        )

        self._show_all_resources = self.config_entry.options.get(
            CONF_SHOW_ALL_RESOURCES,
            False,
        )

        self._import_historical_data = self.config_entry.options.get(
            CONF_IMPORT_HISTORICAL_DATA,
            True,
        )

        self._sensor_index = 0

        if entry_data is None:
            return await self.async_step_general()

        if (
            self._sensors
            and not self._sensor_types
        ):
            return await self.async_step_initial_sensor_setup()

        if self.config_entry.data.get(CONF_INITIAL_HISTORY_PENDING, False):
            return await self._async_finish_initial_sensor_setup()

        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "general",
                "sensors",
                "single_sensor",
                "history_import",
                "rediscover",
            ],
        )

    async def async_step_initial_sensor_setup(
        self,
        user_input=None,
    ):
        """Show the initial sensor setup menu."""

        return self.async_show_menu(
            step_id="initial_sensor_setup",
            menu_options=[
                "general",
                "sensors",
            ],
        )

    async def async_step_rediscover(self, user_input=None):
        """Reload the entry to discover new sensors and devices."""

        self.hass.config_entries.async_schedule_reload(
            self.config_entry.entry_id
        )

        return self.async_abort(
            reason="rediscovery_started",
        )

    async def async_step_general(self, user_input=None):
        """Configure general GHL options."""

        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(
            identifiers={(DOMAIN, self.config_entry.entry_id)}
        )
        current_name = (
            device.name_by_user
            if device is not None and device.name_by_user
            else self.config_entry.title
        )
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            access_mode = user_input[CONF_ACCESS_MODE]
            show_all_resources = user_input[
                CONF_SHOW_ALL_RESOURCES
            ]
            import_historical_data = user_input[
                CONF_IMPORT_HISTORICAL_DATA
            ]

            name = user_input.get(CONF_NAME, "")
            name_changed = name != self.config_entry.title

            old_host = self.config_entry.data[CONF_HOST]
            old_port = self.config_entry.data[CONF_PORT]
            old_access_mode = self.config_entry.data[
                CONF_ACCESS_MODE
            ]
            old_show_all_resources = (
                self.config_entry.options.get(
                    CONF_SHOW_ALL_RESOURCES,
                    False,
                )
            )
            old_import_historical_data = (
                self.config_entry.options.get(
                    CONF_IMPORT_HISTORICAL_DATA,
                    False,
                )
            )

            connection_changed = (
                host != old_host
                or port != old_port
            )

            data_changed = (
                name_changed
                or host != old_host
                or port != old_port
                or access_mode != old_access_mode
            )

            options_changed = (
                show_all_resources
                != old_show_all_resources
                or import_historical_data
                != old_import_historical_data
            )

            if connection_changed:
                duplicate_entry = next(
                    (
                        entry
                        for entry in self.hass.config_entries.async_entries(
                            DOMAIN
                        )
                        if (
                            entry.entry_id != self.config_entry.entry_id
                            and entry.data.get(CONF_HOST) == host
                            and entry.data.get(CONF_PORT) == port
                        )
                    ),
                    None,
                )

                if duplicate_entry is not None:
                    errors["base"] = "already_configured"

            if not errors:
                new_data = dict(self.config_entry.data)

                new_data[CONF_HOST] = host
                new_data[CONF_PORT] = port
                new_data[CONF_ACCESS_MODE] = access_mode

                if device is not None and (
                    name_changed or name != current_name
                ):
                    device_registry.async_update_device(
                        device.id, name=name, name_by_user=None
                    )

                self.hass.config_entries.async_update_entry(
                    self.config_entry,
                    data=new_data,
                    title=name,
                )

                self._show_all_resources = (
                    show_all_resources
                )
                self._import_historical_data = (
                    import_historical_data
                )

                if (
                    (data_changed or options_changed)
                    and not self.config_entry.update_listeners
                ):
                    self.hass.config_entries.async_schedule_reload(
                        self.config_entry.entry_id
                    )

                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SENSOR_TYPES: self._sensor_types,
                        CONF_SENSOR_UNITS: self._sensor_units,
                        CONF_SHOW_ALL_RESOURCES: (
                            self._show_all_resources
                        ),
                        CONF_IMPORT_HISTORICAL_DATA: (
                            self._import_historical_data
                        ),
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_NAME,
                    description={
                        "suggested_value": (
                            current_name
                            if user_input is None
                            else user_input.get(CONF_NAME, "")
                        )
                    },
                ): str,
                vol.Required(
                    CONF_HOST,
                    default=self.config_entry.data[CONF_HOST],
                ): str,
                vol.Required(
                    CONF_PORT,
                    default=self.config_entry.data[CONF_PORT],
                ): int,
                vol.Required(
                    CONF_ACCESS_MODE,
                    default=self.config_entry.data[CONF_ACCESS_MODE],
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            ACCESS_MODE_READ_ONLY,
                            ACCESS_MODE_FULL_ACCESS,
                        ],
                        translation_key="access_mode",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_SHOW_ALL_RESOURCES,
                    default=self._show_all_resources,
                ): bool,
                vol.Required(
                    CONF_IMPORT_HISTORICAL_DATA,
                    default=self._import_historical_data,
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="general",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_history_import(self, user_input=None):
        """Import historical data for all currently available sources."""

        entry_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        active_import = self.hass.data.get(f"{DOMAIN}_history_imports", {}).get(
            self.config_entry.entry_id
        )
        if (
            active_import is not None
            and active_import._history_worker is not None
            and not active_import._history_worker.done()
        ):
            self._history_owner = active_import
            user_input = {}

        if user_input is None:
            return self.async_show_form(
                step_id="history_import",
                data_schema=vol.Schema({}),
            )

        entry_data = (
            self.hass.data
            .get(DOMAIN, {})
            .get(self.config_entry.entry_id)
        )

        if entry_data is None:
            return self.async_abort(
                reason="entry_not_loaded",
            )

        resources = history_resource_map(
            entry_data["resources"]
        )
        eligible_resources = [
            resource
            for resource in resources.values()
            if (
                sensor_history_is_configured(
                    self.config_entry,
                    resource,
                )
                and sensor_history_should_import(
                    self.config_entry,
                    resource,
                )
            )
        ]

        if not eligible_resources:
            return self.async_abort(
                reason="no_history_sources",
            )

        self._history_initial = False
        translations = await async_get_translations(
            self.hass, self.hass.config.language, "options", {DOMAIN},
        )
        self._history_background_hint = translations.get(
            f"component.{DOMAIN}.options.step.history_import_progress.description",
            "You can close this dialog. The import will continue in the background.",
        )
        return await self.async_step_history_import_progress()

    async def _async_finish_initial_sensor_setup(self):
        """Continue initial setup without another confirmation."""
        if self._import_historical_data:
            translations = await async_get_translations(
                self.hass, self.hass.config.language, "options", {DOMAIN},
            )
            self._history_background_hint = translations.get(
                f"component.{DOMAIN}.options.step.history_import_progress.description",
                "You can close this dialog. The import will continue in the background.",
            )
            self._history_initial = True
            return await self.async_step_history_import_progress()

        new_data = dict(self.config_entry.data)
        new_data.pop(CONF_INITIAL_HISTORY_PENDING, None)
        self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
        return self.async_create_entry(title="", data=self._initial_history_options())

    def _initial_history_options(self):
        """Return the options selected during initial sensor configuration."""
        return {
            CONF_SENSOR_TYPES: self._sensor_types,
            CONF_SENSOR_UNITS: self._sensor_units,
            CONF_SHOW_ALL_RESOURCES: self._show_all_resources,
            CONF_IMPORT_HISTORICAL_DATA: self._import_historical_data,
        }

    async def async_step_history_import_progress(self, user_input=None):
        """Keep the import visible while the single background task runs."""
        self._history_refresh_received.set()
        if self._history_task is None:
            registry = self.hass.data.setdefault(f"{DOMAIN}_history_imports", {})
            if self._history_owner is None:
                active_import = registry.get(self.config_entry.entry_id)
                if (
                    active_import is not None
                    and active_import._history_worker is not None
                    and not active_import._history_worker.done()
                ):
                    self._history_owner = active_import
                else:
                    entry_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
                    if entry_data is None:
                        return self.async_abort(reason="entry_not_loaded")
                    self._history_owner = self
                    self._history_registry = registry
                    registry[self.config_entry.entry_id] = self
                    self._history_worker = self.hass.async_create_task(self._async_run_history_import())
                    self._history_worker.add_done_callback(self._history_background_import_done)
            if self._history_owner is not self:
                self._history_worker = self._history_owner._history_worker
                self._history_initial = self._history_owner._history_initial
            self._history_owner._history_observers.add(self)
            self._history_task = self.hass.async_create_task(self._async_wait_for_history_import())
            self._history_task.add_done_callback(self._history_dialog_task_done)

        history = self._history_owner or self
        if not self._history_task.done():
            progress_action = (
                "history_import_running"
                if history._history_source_name is not None
                else "history_import_preparing"
            )
            placeholders = {
                "source_number": str(history._history_source_number),
                "source_total": str(history._history_source_total),
                "source_name": history._history_source_name or "",
                "records_count": format(history._history_records, ",").replace(",", "'"),
                "background_hint": self._history_background_hint,
            }
            if (
                self.cur_step
                and self.cur_step.get("step_id") == "history_import_progress"
            ):
                # This request already refreshes the text; do not trigger another GET.
                self.cur_step["progress_action"] = progress_action
                self.cur_step["description_placeholders"] = placeholders
            return self.async_show_progress(
                step_id="history_import_progress",
                progress_action=progress_action,
                description_placeholders=placeholders,
                progress_task=self._history_task,
            )

        try:
            self._history_task.result()
        except Exception:
            _LOGGER.exception("Historical GHL data import failed")
            history._history_import_failed = True
            history._history_abort_reason = "history_import_incomplete"
        return self.async_show_progress_done(next_step_id="history_import_finish")

    async def _async_wait_for_history_import(self):
        """Keep the import independent of the dialog's lifetime."""
        try:
            await asyncio.shield(self._history_worker)
        except Exception:
            await self._history_refresh_received.wait()
            raise
        await self._history_refresh_received.wait()

    def _history_dialog_task_done(self, task):
        """Keep reading when HA cancels the closed dialog's progress task."""
        if task.cancelled():
            self._history_dialog_closed = True
            if self._history_owner is not None:
                self._history_owner._history_observers.discard(self)

    def _history_background_import_done(self, task):
        """Report background errors after the import dialog was closed."""
        if (
            self._history_registry is not None
            and self._history_registry.get(self.config_entry.entry_id) is self
        ):
            self._history_registry.pop(self.config_entry.entry_id)
            if not self._history_registry:
                self.hass.data.pop(f"{DOMAIN}_history_imports", None)
        if task.cancelled():
            return
        if (error := task.exception()) and not self._history_observers:
            _LOGGER.error(
                "Historical GHL data import failed after the dialog was closed",
                exc_info=(type(error), error, error.__traceback__),
            )

    async def _async_update_history_progress(self, records=None, *, force=False):
        """Refresh source/count text at most once per second."""
        if records is not None:
            self._history_records = records
        now = monotonic()
        if not force and now - self._history_last_update < 1:
            return
        self._history_last_update = now
        dialogs = tuple(self._history_observers) if self._history_owner is self else (self,)
        for dialog in dialogs:
            if dialog._history_dialog_closed:
                continue
            if dialog.cur_step and dialog.cur_step.get("step_id") == "history_import_progress":
                # Only one text refresh may be outstanding for each dialog.
                if dialog._history_refresh_received.is_set():
                    dialog._history_refresh_received.clear()
                    dialog.async_notify_flow_changed()

    def _history_resource_name(self, resource, translations):
        """Use the existing description-editor labels for history sources."""
        if (
            resource.resource in DESCRIPTION_RESOURCE_TRANSLATION_KEYS
            and resource.index is not None
        ):
            translation_key = DESCRIPTION_RESOURCE_TRANSLATION_KEYS[
                resource.resource
            ]
            template = translations.get(
                f"component.{DOMAIN}.entity.select.{translation_key}.name",
                DESCRIPTION_RESOURCE_FALLBACKS[resource.resource],
            )
            resource_name = template.format(index=resource.index + 1)
        else:
            resource_name = (
                resource.resource
                if resource.index is None
                else f"{resource.resource}[{resource.index}]"
            )

        if resource.description is not None:
            resource_name = f"{resource_name} - {resource.description}"
        return resource_name

    async def _async_run_history_import(self):
        """Prepare initial entities, then import with source/count updates."""
        if self._history_initial:
            entry_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
            if entry_data is None:
                self._history_abort_reason = "entry_not_loaded"
                return
            options = self._initial_history_options()
            # This task performs the reload itself and waits for its entities.
            entry_data["history_flow_options"] = options
            self.hass.config_entries.async_update_entry(self.config_entry, options=options)
            if not await self.hass.config_entries.async_reload(self.config_entry.entry_id):
                self._history_abort_reason = "entry_not_loaded"
                return

        entry_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id)
        if entry_data is None:
            self._history_abort_reason = "entry_not_loaded"
            return

        resources = history_resource_map(entry_data["resources"])
        eligible_resources = [
            resource for resource in resources.values()
            if sensor_history_is_configured(self.config_entry, resource)
            and sensor_history_should_import(self.config_entry, resource)
        ]
        if not eligible_resources and not self._history_initial:
            self._history_abort_reason = "no_history_sources"
            return

        translations = await async_get_translations(
            self.hass, self.hass.config.language, "entity", {DOMAIN},
        )
        records_label = {
            "de": "Datensätze",
            "en": "records",
            "es": "registros",
            "fr": "enregistrements",
        }.get(self.hass.config.language, "records")
        summary_lines = []
        completed_resources = set(
            self.config_entry.data.get(CONF_HISTORY_PRESENT_RESOURCES, [])
        )
        self._history_source_total = len(eligible_resources)
        for source_number, resource in enumerate(eligible_resources, 1):
            resource_name = self._history_resource_name(resource, translations)
            self._history_source_number = source_number
            self._history_source_name = resource_name
            self._history_records = 0
            await self._async_update_history_progress(force=True)
            result = await async_import_resource_history(
                hass=self.hass,
                entry=self.config_entry,
                api=entry_data["api"],
                resource=resource,
                progress_callback=self._async_update_history_progress,
            )
            await self._async_update_history_progress(force=True)
            if not result.success:
                self._history_import_failed = True
            else:
                completed_resources.add(history_resource_key(resource))
                if self._history_initial:
                    new_data = dict(self.config_entry.data)
                    new_data[CONF_HISTORY_PRESENT_RESOURCES] = sorted(completed_resources)
                    self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)
            summary_lines.append(
                f"{resource_name}: {result.records_found} {records_label}"
            )
        self._history_summary = "\n".join(summary_lines)

        if self._history_initial:
            new_data = dict(self.config_entry.data)
            new_data.pop(CONF_INITIAL_HISTORY_PENDING, None)
            self.hass.config_entries.async_update_entry(self.config_entry, data=new_data)

    async def async_step_history_import_finish(self, user_input=None):
        """Finish initial setup automatically or show the manual summary."""
        history = self._history_owner or self
        if history._history_abort_reason is not None:
            return self.async_abort(reason=history._history_abort_reason)
        if history._history_initial:
            return self.async_create_entry(title="", data=history._initial_history_options())
        return self.async_abort(
            reason=(
                "history_import_result_incomplete"
                if history._history_import_failed
                else "history_import_result"
            ),
            description_placeholders={"summary": history._history_summary},
        )

    async def async_step_history_import_result(self, user_input=None):
        """Show the result of a manual historical data import."""

        if user_input is None:
            return self.async_show_form(
                step_id="history_import_result",
                data_schema=vol.Schema({}),
                description_placeholders={"summary": self._history_summary},
            )

        if getattr(self, "_history_import_failed", False):
            return self.async_abort(
                reason="history_import_incomplete",
            )

        return self.async_abort(
            reason="history_import_complete",
        )

    async def async_step_single_sensor(self, user_input=None):
        """Select one discovered GHL sensor to configure."""

        if not self._sensors:
            return self.async_abort(reason="no_sensors")

        if user_input is not None:
            selected_sensor = user_input["sensor_index"]
            self._sensor_index = next(
                index
                for index, resource in enumerate(self._sensors)
                if str(resource.index) == selected_sensor
            )
            self._single_sensor = True
            return await self.async_step_sensor()

        translations = await async_get_translations(
            self.hass,
            self.hass.config.language,
            "selector",
            {DOMAIN},
        )
        sensor_options = []
        for resource in self._sensors:
            sensor_type = self._sensor_types.get(
                str(resource.index), SENSOR_TYPE_UNKNOWN,
            )
            type_name = translations.get(
                f"component.{DOMAIN}.selector.sensor_type.options.{sensor_type}",
                sensor_type,
            )
            sensor_options.append(
                {
                    "value": str(resource.index),
                    "label": (
                        f"{resource.index + 1} – {resource.description} – {type_name}"
                        if resource.description
                        else f"{resource.index + 1} – {type_name}"
                    ),
                }
            )

        return self.async_show_form(
            step_id="single_sensor",
            data_schema=vol.Schema(
                {
                    vol.Required("sensor_index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=sensor_options,
                            mode=selector.SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )

    async def async_step_sensors(self, user_input=None):
        """Start GHL sensor configuration."""

        if not self._sensors:
            return self.async_abort(
                reason="no_sensors",
            )

        self._sensor_index = 0
        self._single_sensor = False

        return await self.async_step_sensor()

    async def async_step_sensor(self, user_input=None):
        """Configure the type of a discovered GHL sensor."""

        if user_input is not None:
            sensor_resource = self._sensors[self._sensor_index]
            sensor_key = str(sensor_resource.index)
            sensor_type = user_input[CONF_SENSOR_TYPE]

            self._sensor_types[sensor_key] = sensor_type

            if sensor_type == SENSOR_TYPE_CONDUCTIVITY_SEAWATER:
                return await self.async_step_sensor_unit()

            self._sensor_units.pop(sensor_key, None)

            self._sensor_index += 1

            if self._single_sensor or self._sensor_index >= len(self._sensors):
                if self.config_entry.data.get(CONF_INITIAL_HISTORY_PENDING, False):
                    return await self._async_finish_initial_sensor_setup()
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SENSOR_TYPES: self._sensor_types,
                        CONF_SENSOR_UNITS: self._sensor_units,
                        CONF_SHOW_ALL_RESOURCES: (
                            self._show_all_resources
                        ),
                        CONF_IMPORT_HISTORICAL_DATA: (
                            self._import_historical_data
                        ),
                    },
                )

        sensor_resource = self._sensors[self._sensor_index]

        sensor_name = (
            sensor_resource.description
            if sensor_resource.description is not None
            else f"Sensor {sensor_resource.index + 1}"
        )

        current_sensor_type = self._sensor_types.get(
            str(sensor_resource.index),
            SENSOR_TYPE_UNKNOWN,
        )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SENSOR_TYPE,
                    default=current_sensor_type,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            SENSOR_TYPE_UNKNOWN,
                            SENSOR_TYPE_HIDDEN,
                            SENSOR_TYPE_TEMPERATURE,
                            SENSOR_TYPE_PH,
                            SENSOR_TYPE_REDOX,
                            SENSOR_TYPE_CONDUCTIVITY_FRESHWATER,
                            SENSOR_TYPE_CONDUCTIVITY_SEAWATER,
                            SENSOR_TYPE_OXYGEN,
                            SENSOR_TYPE_HUMIDITY,
                            SENSOR_TYPE_AIR_TEMPERATURE,
                            SENSOR_TYPE_VOLTAGE,
                        ],
                        translation_key="sensor_type",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        return self.async_show_form(
            step_id="sensor",
            data_schema=data_schema,
            description_placeholders={
                "sensor_name": sensor_name,
                "sensor_number": str(sensor_resource.index + 1),
            },
        )

    async def async_step_sensor_unit(self, user_input=None):
        """Configure the unit of a seawater conductivity sensor."""

        sensor_resource = self._sensors[self._sensor_index]
        sensor_key = str(sensor_resource.index)

        if user_input is not None:
            self._sensor_units[sensor_key] = user_input[CONF_SENSOR_UNIT]

            self._sensor_index += 1

            if self._single_sensor or self._sensor_index >= len(self._sensors):
                if self.config_entry.data.get(CONF_INITIAL_HISTORY_PENDING, False):
                    return await self._async_finish_initial_sensor_setup()
                return self.async_create_entry(
                    title="",
                    data={
                        CONF_SENSOR_TYPES: self._sensor_types,
                        CONF_SENSOR_UNITS: self._sensor_units,
                        CONF_SHOW_ALL_RESOURCES: (
                            self._show_all_resources
                        ),
                        CONF_IMPORT_HISTORICAL_DATA: (
                            self._import_historical_data
                        ),
                    },
                )

            return await self.async_step_sensor()

        current_sensor_unit = self._sensor_units.get(
            sensor_key,
            SENSOR_UNIT_MS,
        )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_SENSOR_UNIT,
                    default=current_sensor_unit,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            SENSOR_UNIT_MS,
                            SENSOR_UNIT_PSU,
                            SENSOR_UNIT_KG_L,
                        ],
                        translation_key="sensor_unit",
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
            }
        )

        sensor_name = (
            sensor_resource.description
            if sensor_resource.description is not None
            else f"Sensor {sensor_resource.index + 1}"
        )

        return self.async_show_form(
            step_id="sensor_unit",
            data_schema=data_schema,
            description_placeholders={
                "sensor_name": sensor_name,
                "sensor_number": str(sensor_resource.index + 1),
            },
        )
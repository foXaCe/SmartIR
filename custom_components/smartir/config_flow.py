"""Config and options flow for the SmartIR integration."""

from __future__ import annotations

from typing import Any

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
import voluptuous as vol

from .const import (
    CONF_CONTROLLER_DATA,
    CONF_CONTROLLER_TYPE,
    CONF_DELAY,
    CONF_DEVICE_CODE,
    CONF_DEVICE_TYPE,
    CONF_HUMIDITY_SENSOR,
    CONF_NAME,
    CONF_POWER_SENSOR,
    CONF_POWER_SENSOR_RESTORE_STATE,
    CONF_TEMPERATURE_SENSOR,
    CONTROLLER_TYPES,
    DEFAULT_DELAY,
    DEVICE_TYPES,
    DOMAIN,
)

_DEVICE_CODE_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(min=1, step=1, mode=selector.NumberSelectorMode.BOX)
)
_DELAY_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=0.1, max=10, step=0.1, mode=selector.NumberSelectorMode.BOX, unit_of_measurement="s"
    )
)
_REMOTE_SELECTOR = selector.EntitySelector(selector.EntitySelectorConfig(domain="remote"))


def _sensor_selector(device_class: str) -> selector.EntitySelector:
    """Return an entity selector for a sensor of the given device class."""
    return selector.EntitySelector(selector.EntitySelectorConfig(domain="sensor", device_class=device_class))


def _opt(key: str, current: dict[str, Any]) -> vol.Optional:
    """Return a ``vol.Optional`` pre-filled with the current value when present."""
    value = current.get(key)
    if value is not None:
        return vol.Optional(key, default=value)
    return vol.Optional(key)


def _sensor_fields(device_type: str, current: dict[str, Any]) -> dict[Any, Any]:
    """Return the device-type-specific sensor fields for a schema."""
    fields: dict[Any, Any] = {}
    if device_type == "climate":
        fields[_opt(CONF_TEMPERATURE_SENSOR, current)] = _sensor_selector("temperature")
        fields[_opt(CONF_HUMIDITY_SENSOR, current)] = _sensor_selector("humidity")
    fields[_opt(CONF_POWER_SENSOR, current)] = _sensor_selector("power")
    if device_type == "climate":
        fields[
            vol.Optional(
                CONF_POWER_SENSOR_RESTORE_STATE,
                default=current.get(CONF_POWER_SENSOR_RESTORE_STATE, False),
            )
        ] = selector.BooleanSelector()
    return fields


class SmartIRConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for SmartIR."""

    VERSION = 2

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.device_type: str | None = None
        self.controller_type: str | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> SmartIROptionsFlow:
        """Return the options flow handler."""
        return SmartIROptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Select the device type."""
        if user_input is not None:
            self.device_type = user_input[CONF_DEVICE_TYPE]
            return await self.async_step_controller()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_DEVICE_TYPE): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(DEVICE_TYPES),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="device_type",
                        )
                    )
                }
            ),
        )

    async def async_step_controller(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Select the controller type."""
        if user_input is not None:
            self.controller_type = user_input[CONF_CONTROLLER_TYPE]
            return await self.async_step_device_config()

        return self.async_show_form(
            step_id="controller",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_CONTROLLER_TYPE): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=list(CONTROLLER_TYPES),
                            mode=selector.SelectSelectorMode.DROPDOWN,
                            translation_key="controller",
                        )
                    )
                }
            ),
        )

    async def async_step_device_config(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure the device (code, controller entity, delay, sensors)."""
        assert self.device_type is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            controller_data = user_input.get(CONF_CONTROLLER_DATA)
            if controller_data and self.hass.states.get(controller_data) is None:
                errors[CONF_CONTROLLER_DATA] = "controller_not_found"

            if not errors:
                assert self.controller_type is not None
                device_code = int(user_input[CONF_DEVICE_CODE])
                unique_id = f"smartir_{self.device_type}_{device_code}_{controller_data}"
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                device_name = user_input.get(CONF_NAME) or f"SmartIR {DEVICE_TYPES[self.device_type]}"
                controller_name = CONTROLLER_TYPES[self.controller_type]

                data: dict[str, Any] = {
                    CONF_DEVICE_TYPE: self.device_type,
                    CONF_CONTROLLER_TYPE: self.controller_type,
                    CONF_NAME: device_name,
                    CONF_DEVICE_CODE: device_code,
                    CONF_CONTROLLER_DATA: controller_data,
                    CONF_DELAY: user_input.get(CONF_DELAY, DEFAULT_DELAY),
                }
                for opt in (
                    CONF_TEMPERATURE_SENSOR,
                    CONF_HUMIDITY_SENSOR,
                    CONF_POWER_SENSOR,
                    CONF_POWER_SENSOR_RESTORE_STATE,
                ):
                    if user_input.get(opt) is not None:
                        data[opt] = user_input[opt]

                return self.async_create_entry(title=f"{device_name} ({controller_name})", data=data)

        schema: dict[Any, Any] = {
            vol.Optional(CONF_NAME): selector.TextSelector(),
            vol.Required(CONF_DEVICE_CODE): _DEVICE_CODE_SELECTOR,
            vol.Required(CONF_CONTROLLER_DATA): _REMOTE_SELECTOR,
            vol.Optional(CONF_DELAY, default=DEFAULT_DELAY): _DELAY_SELECTOR,
            **_sensor_fields(self.device_type, {}),
        }

        return self.async_show_form(
            step_id="device_config",
            data_schema=vol.Schema(schema),
            errors=errors,
            description_placeholders={
                "device_code_help_url": f"https://github.com/foXaCe/SmartIR/tree/main/codes/{self.device_type}"
            },
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Reconfigure an existing device (code, controller entity, delay)."""
        entry = self._get_reconfigure_entry()
        current = {**entry.data, **entry.options}
        errors: dict[str, str] = {}

        if user_input is not None:
            controller_data = user_input.get(CONF_CONTROLLER_DATA)
            if controller_data and self.hass.states.get(controller_data) is None:
                errors[CONF_CONTROLLER_DATA] = "controller_not_found"

            if not errors:
                updates = {**user_input, CONF_DEVICE_CODE: int(user_input[CONF_DEVICE_CODE])}
                # async_update_and_abort (not *_reload_*) so the single reload is
                # driven by the update listener registered in __init__.py.
                return self.async_update_and_abort(entry, data_updates=updates)

        schema = {
            vol.Required(CONF_DEVICE_CODE, default=current.get(CONF_DEVICE_CODE)): _DEVICE_CODE_SELECTOR,
            vol.Required(CONF_CONTROLLER_DATA, default=current.get(CONF_CONTROLLER_DATA)): _REMOTE_SELECTOR,
            vol.Optional(CONF_DELAY, default=current.get(CONF_DELAY, DEFAULT_DELAY)): _DELAY_SELECTOR,
        }

        return self.async_show_form(step_id="reconfigure", data_schema=vol.Schema(schema), errors=errors)


class SmartIROptionsFlow(config_entries.OptionsFlow):
    """Handle the SmartIR options flow."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> config_entries.ConfigFlowResult:
        """Manage the SmartIR device options."""
        if user_input is not None:
            options = {**user_input, CONF_DEVICE_CODE: int(user_input[CONF_DEVICE_CODE])}
            return self.async_create_entry(data=options)

        current = {**self.config_entry.data, **self.config_entry.options}
        device_type = current.get(CONF_DEVICE_TYPE, "climate")

        schema: dict[Any, Any] = {
            _opt(CONF_NAME, current): selector.TextSelector(),
            vol.Optional(CONF_DEVICE_CODE, default=current.get(CONF_DEVICE_CODE, 1)): _DEVICE_CODE_SELECTOR,
            _opt(CONF_CONTROLLER_DATA, current): _REMOTE_SELECTOR,
            vol.Optional(CONF_DELAY, default=current.get(CONF_DELAY, DEFAULT_DELAY)): _DELAY_SELECTOR,
            **_sensor_fields(device_type, current),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "device_code_help_url": f"https://github.com/foXaCe/SmartIR/tree/main/codes/{device_type}"
            },
        )

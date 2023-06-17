"""Config flow for Enphase Envoy integration."""
from __future__ import annotations

import contextlib
import logging
from typing import Any

from .envoy_reader import EnvoyReader
import httpx
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components import zeroconf
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN, CONF_SERIAL

_LOGGER = logging.getLogger(__name__)

ENVOY = "Envoy"


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> EnvoyReader:
    """Validate the user input allows us to connect."""
    envoy_reader = EnvoyReader(
        data[CONF_HOST],
        enlighten_user=data[CONF_USERNAME],
        enlighten_pass=data[CONF_PASSWORD],
        inverters=False,
        enlighten_serial_num=data[CONF_SERIAL],
    )

    try:
        await envoy_reader.getData()
    except httpx.HTTPStatusError as err:
        raise InvalidAuth from err
    except (RuntimeError, httpx.HTTPError) as err:
        raise CannotConnect from err

    return envoy_reader


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

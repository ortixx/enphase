"""The Enphase Envoy integration."""
from __future__ import annotations

import logging
from datetime import timedelta

import async_timeout
import homeassistant.config_entries
import httpx
from homeassistant.const import CONF_HOST,CONF_NAME,CONF_PASSWORD,CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator,UpdateFailed

from custom_components.enphase_envoy.const import COORDINATOR,DOMAIN,NAME,PLATFORMS,BINARY_SENSORS,SENSORS, \
    PHASE_SENSORS,CONF_SERIAL,READER
from .envoy_reader import EnvoyReader

SCAN_INTERVAL = timedelta(seconds=10)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant,entry: homeassistant.ConfigEntry) -> bool:
    """Set up Enphase Envoy from a config entry."""

    config = entry.data
    name = config[CONF_NAME]

    envoy_reader = EnvoyReader(
        config[CONF_HOST],
        enlighten_user=config[CONF_USERNAME],
        enlighten_pass=config[CONF_PASSWORD],
        inverters=True,
        enlighten_serial_num=config[CONF_SERIAL],
    )

    async def async_update_data():
        """Fetch data from API endpoint."""
        data = {}
        async with async_timeout.timeout(60):
            try:
                await envoy_reader.getData()
            except httpx.HTTPStatusError as err:
                raise ConfigEntryAuthFailed from err
            except httpx.HTTPError as err:
                raise UpdateFailed(f"Error communicating with API: {err}") from err

            for description in BINARY_SENSORS:
                if description.key == "relays":
                    data[description.key] = await envoy_reader.relay_status()

                elif description.key == "firmware":
                    envoy_info = await envoy_reader.envoy_info()
                    data[description.key] = envoy_info.get("update_status", None)

            for description in SENSORS:
                if description.key == "inverters":
                    data[
                        "inverters_production"
                    ] = await envoy_reader.inverters_production()
                    data["inverters_status"] = await envoy_reader.inverters_status()

                elif description.key.startswith("inverters_"):
                    continue

                elif description.key == "batteries":
                    battery_data = await envoy_reader.battery_storage()
                    if isinstance(battery_data, list) and len(battery_data) > 0:
                        battery_dict = {}
                        for item in battery_data:
                            battery_dict[item["serial_num"]] = item

                        data[description.key] = battery_dict

                elif description.key in [
                    "current_battery_capacity",
                    "total_battery_percentage",
                ]:
                    continue

                else:
                    data[description.key] = await getattr(
                        envoy_reader, description.key
                    )()

            for description in PHASE_SENSORS:
                if description.key.startswith("production_"):
                    data[description.key] = await envoy_reader.production_phase(
                        description.key
                    )
                elif description.key.startswith("consumption_"):
                    data[description.key] = await envoy_reader.consumption_phase(
                        description.key
                    )
                elif description.key.startswith("daily_production_"):
                    data[description.key] = await envoy_reader.daily_production_phase(
                        description.key
                    )
                elif description.key.startswith("daily_consumption_"):
                    data[description.key] = await envoy_reader.daily_consumption_phase(
                        description.key
                    )
                elif description.key.startswith("lifetime_production_"):
                    data[
                        description.key
                    ] = await envoy_reader.lifetime_production_phase(description.key)
                elif description.key.startswith("lifetime_consumption_"):
                    data[
                        description.key
                    ] = await envoy_reader.lifetime_consumption_phase(description.key)

            data["grid_status"] = await envoy_reader.grid_status()
            data["production_power"] = await envoy_reader.production_power()
            data["envoy_info"] = await envoy_reader.envoy_info()
            data["inverters_info"] = await envoy_reader.inverters_info()

            _LOGGER.debug("Retrieved data from API: %s", data)

            return data

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"envoy {name}",
        update_method=async_update_data,
        update_interval=SCAN_INTERVAL,
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryAuthFailed:
        envoy_reader.get_inverters = False
        await coordinator.async_config_entry_first_refresh()

    if not entry.unique_id:
        try:
            serial = await envoy_reader.get_full_serial_number()
        except httpx.HTTPError:
            pass
        else:
            hass.config_entries.async_update_entry(entry, unique_id=serial)

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        COORDINATOR: coordinator,
        NAME: name,
        READER: envoy_reader,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant,entry: homeassistant.config_entries.ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

"""Support for Enphase Envoy solar energy monitor."""
from __future__ import annotations

import datetime

from time import strftime, localtime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    COORDINATOR,
    DOMAIN,
    NAME,
    SENSORS,
    ICON,
    PHASE_SENSORS,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up envoy sensor platform."""
    data = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = data[COORDINATOR]
    name = data[NAME]

    entities = []
    for sensor_description in SENSORS:
        if sensor_description.key == "inverters":
            if coordinator.data.get("inverters_production") is not None:
                for inverter in coordinator.data["inverters_production"]:
                    device_name = f"Inverter {inverter}"
                    entity_name = f"{device_name} {sensor_description.name}"
                    serial_number = inverter
                    entities.append(
                        EnvoyInverterEntity(
                            sensor_description,
                            entity_name,
                            device_name,
                            serial_number,
                            serial_number,
                            coordinator,
                            config_entry.unique_id,
                        )
                    )
        elif sensor_description.key.startswith("inverters_"):
            if coordinator.data.get("inverters_status") is not None:
                for inverter in coordinator.data["inverters_status"].keys():
                    device_name = f"Inverter {inverter}"
                    entity_name = f"{device_name} {sensor_description.name}"
                    serial_number = inverter
                    entities.append(
                        EnvoyInverterEntity(
                            sensor_description,
                            entity_name,
                            device_name,
                            serial_number,
                            None,
                            coordinator,
                            config_entry.unique_id,
                        )
                    )

        else:
            data = coordinator.data.get(sensor_description.key)
            if data is None:
                continue

            entity_name = f"{name} {sensor_description.name}"
            entities.append(
                CoordinatedEnvoyEntity(
                    sensor_description,
                    entity_name,
                    name,
                    config_entry.unique_id,
                    None,
                    coordinator,
                )
            )

    for sensor_description in PHASE_SENSORS:
        data = coordinator.data.get(sensor_description.key)
        if data is None:
            continue

        entity_name = f"{name} {sensor_description.name}"
        entities.append(
            CoordinatedEnvoyEntity(
                sensor_description,
                entity_name,
                name,
                config_entry.unique_id,
                None,
                coordinator,
            )
        )

    async_add_entities(entities)


class EnvoyEntity(SensorEntity):
    """Envoy entity"""

    def __init__(
        self,
        description,
        name,
        device_name,
        device_serial_number,
        serial_number,
    ):
        """Initialize Envoy entity."""
        self.entity_description = description
        self._name = name
        self._serial_number = serial_number
        self._device_name = device_name
        self._device_serial_number = device_serial_number

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        if self._serial_number:
            return self._serial_number
        if self._device_serial_number:
            return f"{self._device_serial_number}_{self.entity_description.key}"

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return None


class CoordinatedEnvoyEntity(EnvoyEntity, CoordinatorEntity):
    def __init__(
        self,
        description,
        name,
        device_name,
        device_serial_number,
        serial_number,
        coordinator,
    ):
        EnvoyEntity.__init__(
            self, description, name, device_name, device_serial_number, serial_number
        )
        CoordinatorEntity.__init__(self, coordinator)
        serial_number = None

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device_info of the device."""
        if not self._device_serial_number:
            return None

        sw_version = None
        hw_version = None
        if self.coordinator.data.get("envoy_info"):
            sw_version = self.coordinator.data.get("envoy_info").get("software", None)
            hw_version = self.coordinator.data.get("envoy_info").get("pn", None)

        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_serial_number))},
            manufacturer="Enphase",
            model="Envoy",
            name=self._device_name,
            sw_version=sw_version,
            hw_version=hw_version,
        )


class EnvoyInverterEntity(CoordinatorEntity, SensorEntity):
    """Envoy inverter entity."""

    def __init__(
        self,
        description,
        name,
        device_name,
        device_serial_number,
        serial_number,
        coordinator,
        parent_device,
    ):
        self.entity_description = description
        self._name = name
        self._serial_number = serial_number
        self._device_name = device_name
        self._device_serial_number = device_serial_number
        self._parent_device = parent_device
        CoordinatorEntity.__init__(self, coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        if self._serial_number:
            return self._serial_number
        if self._device_serial_number:
            return f"{self._device_serial_number}_{self.entity_description.key}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.entity_description.key.startswith("inverters_"):
            if self.coordinator.data.get("inverters_status") is not None:
                return (
                    self.coordinator.data.get("inverters_status")
                    .get(self._device_serial_number)
                    .get(self.entity_description.key[10:])
                )
        elif self.coordinator.data.get("inverters_production") is not None:
            return (
                self.coordinator.data.get("inverters_production")
                .get(self._device_serial_number)
                .get("watt")
            )

        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if self.entity_description.key.startswith("inverters_"):
            if self.coordinator.data.get("inverters_status") is not None:
                value = (
                    self.coordinator.data.get("inverters_status")
                    .get(self._device_serial_number)
                    .get("report_date")
                )
                return {"last_reported": value}
        elif self.coordinator.data.get("inverters_production") is not None:
            value = (
                self.coordinator.data.get("inverters_production")
                .get(self._serial_number)
                .get("report_date")
            )
            return {"last_reported": value}

        return None

    @property
    def device_info(self) -> DeviceInfo | None:
        """Return the device_info of the device."""
        if not self._device_serial_number:
            return None

        sw_version = None
        hw_version = None
        if self.coordinator.data.get("inverters_info") and self.coordinator.data.get(
            "inverters_info"
        ).get(self._device_serial_number):
            sw_version = (
                self.coordinator.data.get("inverters_info")
                .get(self._device_serial_number)
                .get("img_pnum_running")
            )
            hw_version = (
                self.coordinator.data.get("inverters_info")
                .get(self._device_serial_number)
                .get("part_num")
            )

        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_serial_number))},
            manufacturer="Enphase",
            model="Inverter",
            name=self._device_name,
            via_device=(DOMAIN, self._parent_device),
            sw_version=sw_version,
            hw_version=hw_version,
        )

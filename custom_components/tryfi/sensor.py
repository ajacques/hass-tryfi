"""Platform for sensor integration."""
import logging

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    PERCENTAGE,
    STATE_UNKNOWN,
    UnitOfLength,
    UnitOfTemperature,
    UnitOfTime
)
from homeassistant.components.datetime import DateTimeEntity
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)
from pytryfi import FiPet
import datetime

from .const import DOMAIN, SENSOR_STATS_BY_TIME, SENSOR_STATS_BY_TYPE

LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Add sensors for passed config_entry in HA."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]

    tryfi = coordinator.data

    new_devices = []
    for pet in tryfi.pets:
        LOGGER.debug(f"Adding Pet Battery Sensor: {pet}")
        new_devices.append(TryFiBatterySensor(hass, pet, coordinator))
        for statType in SENSOR_STATS_BY_TYPE:
            for statTime in SENSOR_STATS_BY_TIME:
                LOGGER.debug(f"Adding Pet Stat: {pet}")
                new_devices.append(
                    PetStatsSensor(hass, pet, coordinator, statType, statTime)
                )
        LOGGER.debug(f"Adding Pet Generic Sensor: {pet}")
        new_devices.append(PetGenericSensor(hass, pet, coordinator, "Activity Type"))
        new_devices.append(PetGenericSensor(hass, pet, coordinator, "Current Place Name"))
        new_devices.append(PetGenericSensor(hass, pet, coordinator, "Current Place Address"))
        new_devices.append(PetGenericSensor(hass, pet, coordinator, "Connection State"))
        new_devices.append(PetGenericSensor(hass, pet, coordinator, "Connected To"))
        new_devices.append(PetGenericSensor(hass, pet, coordinator, "Temperature"))
        new_devices.append(PetDateTimeSensor(pet, coordinator, "Location Next Update"))
        

    for base in tryfi.bases:
        LOGGER.debug(f"Adding Base: {base}")
        new_devices.append(TryFiBaseSensor(hass, base, coordinator))
    if new_devices:
        async_add_devices(new_devices)


class PetDateTimeSensor(CoordinatorEntity, DateTimeEntity):
    def __init__(self, pet: FiPet, coordinator, statType: str):
        super().__init__(coordinator)
        self._pet = pet
        self._statType = statType

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self._pet.name} {self._statType}"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        formattedType = self._statType.lower().replace(" ", "-")
        return f"{self._pet.petId}-{formattedType}"

    @property
    def native_value(self) -> datetime.datetime | None:
        if self._statType == "Location Next Update":
            return self._pet.locationNextEstimatedUpdate

class TryFiBaseSensor(CoordinatorEntity, Entity):
    def __init__(self, hass, base, coordinator):
        self._hass = hass
        self._baseId = base.baseId
        self._online = base.online
        self._base = base
        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.base.name}"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"{self.base.baseId}"

    @property
    def baseId(self):
        return self._baseId

    @property
    def base(self):
        return self.coordinator.data.getBase(self.baseId)

    @property
    def device_id(self):
        return self.unique_id

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return None

    @property
    def state(self):
        if self.base.online:
            return "Online"
        else:
            return "Offline"

    @property
    def icon(self):
        return "mdi:wifi"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.base.baseId)},
            "name": self.base.name,
            "manufacturer": "TryFi",
            "model": "TryFi Base",
            # "sw_version": self.pet.device.buildId,
        }

class PetGenericSensor(CoordinatorEntity, Entity):
    """Representation of a Sensor."""

    def __init__(self, hass, pet, coordinator, statType):
        self._hass = hass
        self._petId = pet.petId
        self._statType = statType
        super().__init__(coordinator)
    
    @property
    def statType(self):
        return self._statType

    @property
    def statTime(self):
        return self._statTime

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.pet.name} {self.statType.title()}"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        formattedType = self.statType.lower().replace(" ", "-")
        return f"{self.pet.petId}-{formattedType}"

    @property
    def petId(self):
        return self._petId

    @property
    def pet(self):
        return self.coordinator.data.getPet(self.petId)

    @property
    def device(self):
        return self.pet.device

    @property
    def device_id(self):
        return self.unique_id

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self.statType.upper() == "TEMPERATURE":
            return "temperature"
        else:
            return None

    @property
    def icon(self):
        if self.statType == "Activity Type":
            return "mdi:run"
        elif self.statType == "Current Place Name":
            return "mdi:earth"
        elif self.statType == "Current Place Address":
            return "mdi:map-marker"
        elif self.statType == "Connected To":
            return "mdi:human-greeting-proximity"
        elif self.statType == "Temperature":
            return "mdi:thermometer-lines"

    @property
    def state(self):
        if self.statType == "Activity Type":
            return self.pet.getActivityType() or STATE_UNKNOWN
        elif self.statType == "Current Place Name":
            return self.pet.getCurrPlaceName() or STATE_UNKNOWN
        elif self.statType == "Current Place Address":
            return self.pet.getCurrPlaceAddress() or STATE_UNKNOWN
        elif self.statType == "Connection State":
            return self.pet.device.connectionStateType
        elif self.statType == "Connected To":
            return self.pet.device.connectedTo
        elif self.statType == "Temperature":
            return self.device.temperature or STATE_UNKNOWN

    @property
    def unit_of_measurement(self):
        if self.statType.upper() == "TEMPERATURE":
            return UnitOfTemperature.CELSIUS
        else:
            return None

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.pet.petId)},
            "name": self.pet.name,
            "manufacturer": "TryFi",
            "model": self.pet.breed,
            "sw_version": self.pet.device.buildId,
        }

class PetStatsSensor(CoordinatorEntity, Entity):
    """Representation of a Sensor."""

    def __init__(self, hass, pet, coordinator, statType, statTime):
        self._hass = hass
        self._petId = pet.petId
        self._statType = statType
        self._statTime = statTime
        super().__init__(coordinator)

    @property
    def statType(self):
        return self._statType

    @property
    def statTime(self):
        return self._statTime

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.pet.name} {self.statTime.title()} {self.statType.title()}"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"{self.pet.petId}-{self.statTime.lower()}-{self.statType.lower()}"

    @property
    def petId(self):
        return self._petId

    @property
    def pet(self):
        return self.coordinator.data.getPet(self.petId)

    @property
    def device(self):
        return self.pet.device

    @property
    def device_id(self):
        return self.unique_id

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        if self.statType.upper() == "DISTANCE":
            return "distance"
        else:
            return None

    @property
    def icon(self):
        return "mdi:map-marker-distance"

    @property
    def state(self):
        statType = self.statType.upper()
        if statType == "STEPS":
            if self.statTime.upper() == "DAILY":
                return self.pet.dailySteps
            elif self.statTime.upper() == "WEEKLY":
                return self.pet.weeklySteps
            elif self.statTime.upper() == "MONTHLY":
                return self.pet.monthlySteps
        elif statType == "DISTANCE":
            if self.statTime.upper() == "DAILY":
                return round(self.pet.dailyTotalDistance / 1000, 2)
            elif self.statTime.upper() == "WEEKLY":
                return round(self.pet.weeklyTotalDistance / 1000, 2)
            elif self.statTime.upper() == "MONTHLY":
                return round(self.pet.monthlyTotalDistance / 1000, 2)
        elif statType == "NAP":
            if self.statTime.upper() == "DAILY":
                return round(self.pet.dailyNap / 60, 2)
            elif self.statTime.upper() == "WEEKLY":
                return round(self.pet.weeklyNap / 60, 2)
            elif self.statTime.upper() == "MONTHLY":
                return round(self.pet.monthlyNap / 60, 2)
        elif statType == "SLEEP":
            if self.statTime.upper() == "DAILY":
                return round(self.pet.dailySleep / 60, 2)
            elif self.statTime.upper() == "WEEKLY":
                return round(self.pet.weeklySleep / 60, 2)
            elif self.statTime.upper() == "MONTHLY":
                return round(self.pet.monthlySleep / 60, 2)
        elif statType == "GOAL":
            if self.statTime.upper() == "DAILY":
                return self.pet.dailyGoal
            elif self.statTime.upper() == "WEEKLY":
                return self.pet.weeklyGoal
            elif self.statTime.upper() == "MONTHLY":
                return self.pet.monthlyGoal
        else:
            return None

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        if self.statType.upper() == "DISTANCE":
            return UnitOfLength.KILOMETERS
        elif self.statType.upper() == "SLEEP":
            return UnitOfTime.MINUTES
        elif self.statType.upper() == "NAP":
            return UnitOfTime.MINUTES
        else:
            return "steps"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.pet.petId)},
            "name": self.pet.name,
            "manufacturer": "TryFi",
            "model": self.pet.breed,
            "sw_version": self.pet.device.buildId,
        }


class TryFiBatterySensor(CoordinatorEntity, Entity):
    """Representation of a Sensor."""

    def __init__(self, hass, pet, coordinator):
        self._hass = hass
        self._petId = pet.petId
        super().__init__(coordinator)

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{self.pet.name} Collar Battery Level"

    @property
    def unique_id(self):
        """Return the ID of this sensor."""
        return f"{self.pet.petId}-battery"

    @property
    def petId(self):
        return self._petId

    @property
    def pet(self):
        return self.coordinator.data.getPet(self.petId)

    @property
    def device(self):
        return self.pet.device

    @property
    def device_id(self):
        return self.unique_id

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return SensorDeviceClass.BATTERY

    @property
    def unit_of_measurement(self):
        """Return the unit_of_measurement of the device."""
        return PERCENTAGE

    @property
    def isCharging(self):
        return bool(self.pet.device.isCharging)

    @property
    def icon(self):
        """Return the icon for the battery."""
        return icon_for_battery_level(
            battery_level=self.batteryPercent, charging=self.isCharging
        )

    @property
    def batteryPercent(self):
        """Return the state of the sensor."""
        return self.pet.device.batteryPercent

    @property
    def state(self):
        return self.batteryPercent

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.pet.petId)},
            "name": self.pet.name,
            "manufacturer": "TryFi",
            "model": self.pet.breed,
            "sw_version": self.pet.device.buildId,
        }

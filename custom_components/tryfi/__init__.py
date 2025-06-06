import asyncio
import logging
from datetime import timedelta

from homeassistant import exceptions
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
from pytryfi import PyTryFi

from .const import (
    DOMAIN,
    PLATFORMS,
)

LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    tryfi = await hass.async_add_executor_job(PyTryFi, entry.data["username"], entry.data["password"])
    hass.data[DOMAIN][entry.entry_id] = tryfi

    # Exceptions are swallowed in the PyTryFi library, so we must assert a 
    # sucessful login before continuing with setup. When not successful,
    # hass will continue to retry setup
    if not hasattr(tryfi, 'currentUser'):
        raise ConfigEntryNotReady

    coordinator = TryFiDataUpdateCoordinator(hass, tryfi, int(entry.data["polling"]))
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # This creates each HA object for each platform your device requires.
    # It's done by calling the `async_setup_entry` function in each platform module.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    # This is called when an entry/configured device is to be removed. The class
    # needs to unload itself, and remove callbacks. See the classes for further
    # details
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_connect_or_timeout(hass, tryfi):
    userId = None
    try:
        userId = tryfi._userId
        if userId != None or "":
            LOGGER.info("Success Connecting to TryFi")
    except Exception as err:
        LOGGER.error("Error connecting to TryFi")
        raise CannotConnect from err


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


class TryFiDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage the refresh of the tryfi data api"""

    def __init__(self, hass, tryfi, pollingRate):
        self._tryfi = tryfi
        self._hass = hass
        self._pollingRate = int(pollingRate)
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=pollingRate),
        )

    @property
    def tryfi(self):
        return self._tryfi

    @property
    def pollingRate(self):
        return self._pollingRate

    async def _async_update_data(self):
        """Update data via library."""
        try:
            await self._hass.async_add_executor_job(self.tryfi.update)
        except Exception as error:
            LOGGER.warning("Failed to update", exc_info=error)
            raise UpdateFailed(error) from error
        return self.tryfi

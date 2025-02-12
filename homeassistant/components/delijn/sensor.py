"""Support for De Lijn (Flemish public transport) information."""
import logging

from pydelijn.api import Passages
from pydelijn.common import HttpException
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by data.delijn.be"

CONF_NEXT_DEPARTURE = "next_departure"
CONF_STOP_ID = "stop_id"
CONF_NUMBER_OF_DEPARTURES = "number_of_departures"

DEFAULT_NAME = "De Lijn"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_NEXT_DEPARTURE): [
            {
                vol.Required(CONF_STOP_ID): cv.string,
                vol.Optional(CONF_NUMBER_OF_DEPARTURES, default=5): cv.positive_int,
            }
        ],
    }
)

AUTO_ATTRIBUTES = (
    "line_number_public",
    "line_transport_type",
    "final_destination",
    "due_at_schedule",
    "due_at_realtime",
    "is_realtime",
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Create the sensor."""
    api_key = config[CONF_API_KEY]

    session = async_get_clientsession(hass)

    sensors = []
    for nextpassage in config[CONF_NEXT_DEPARTURE]:
        sensors.append(
            DeLijnPublicTransportSensor(
                Passages(
                    hass.loop,
                    nextpassage[CONF_STOP_ID],
                    nextpassage[CONF_NUMBER_OF_DEPARTURES],
                    api_key,
                    session,
                    True,
                )
            )
        )

    async_add_entities(sensors, True)


class DeLijnPublicTransportSensor(SensorEntity):
    """Representation of a Ruter sensor."""

    _attr_attribution = ATTRIBUTION
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:bus"

    def __init__(self, line):
        """Initialize the sensor."""
        self.line = line
        self._attr_extra_state_attributes = {}

    async def async_update(self):
        """Get the latest data from the De Lijn API."""
        try:
            await self.line.get_passages()
            self._attr_name = await self.line.get_stopname()
        except HttpException:
            self._attr_available = False
            _LOGGER.error("De Lijn http error")
            return

        self._attr_extra_state_attributes["stopname"] = self._attr_name

        if not self.line.passages:
            self._attr_available = False
            return

        try:
            first = self.line.passages[0]
            if (first_passage := first["due_at_realtime"]) is None:
                first_passage = first["due_at_schedule"]
            self._attr_native_value = first_passage

            for key in AUTO_ATTRIBUTES:
                self._attr_extra_state_attributes[key] = first[key]
            self._attr_extra_state_attributes["next_passages"] = self.line.passages

            self._attr_available = True
        except (KeyError) as error:
            _LOGGER.error("Invalid data received from De Lijn: %s", error)
            self._attr_available = False

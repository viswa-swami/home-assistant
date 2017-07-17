"""
This component provides basic support for Netgear Arlo IP cameras.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/arlo/
"""
import logging
import asyncio
from datetime import timedelta
import async_timeout
import voluptuous as vol
from requests.exceptions import HTTPError, ConnectTimeout

import homeassistant.loader as loader
from homeassistant.helpers import config_validation as cv
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.util import dt as dt_util

REQUIREMENTS = ['pyarlo==0.0.5']

_LOGGER = logging.getLogger(__name__)

CONF_ATTRIBUTION = "Data provided by arlo.netgear.com"

DATA_ARLO = 'data_arlo'
PROPS_ARLO = 'props_arlo'
DEFAULT_BRAND = 'Netgear Arlo'
DOMAIN = 'arlo'

NOTIFICATION_ID = 'arlo_notification'
NOTIFICATION_TITLE = 'Arlo Camera Setup'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


class ArloData(object):
    """An implementation of a Netgear Arlo Camera properties."""

    def __init__(self, hass, config):
        """Initialize the arlo data properties."""
        super().__init__()
        self.hass = hass

        conf = config[DOMAIN]
        username = conf.get(CONF_USERNAME)
        password = conf.get(CONF_PASSWORD)

        persistent_notification = loader.get_component('persistent_notification')
        try:
            from pyarlo import PyArlo

            arlo = PyArlo(username, password, preload=False)
            if not arlo.is_connected:
                return False
            hass.data[DATA_ARLO] = arlo
        except (ConnectTimeout, HTTPError) as ex:
            _LOGGER.error("Unable to connect to Netgar Arlo: %s", str(ex))
            persistent_notification.create(
                hass, 'Error: {}<br />'
                'You will need to restart hass after fixing.'
                ''.format(ex),
                title=NOTIFICATION_TITLE,
                notification_id=NOTIFICATION_ID)
            return False

        self._arlo_session = hass.data.get(DATA_ARLO)
        self._cameras = self._arlo_session.cameras
        self._base_station = self._arlo_session.base_stations
        self._mode = None
        self._camera_battery_levels = {}
        self._motion_status = False
        self._camera_signal_strengths = {}

    def get_battery_level(self, device_id):
        """Camera battery level."""
        if self._camera_battery_levels:
            return self._camera_battery_levels.get(device_id)

    def get_signal_strength(self, device_id):
        """Camera signal strength."""
        if self._camera_signal_strengths:
            return self._camera_signal_strengths.get(device_id)

    def subscribe(self):
        """Subscribe with arlo system."""
        self._arlo_session.update()
        if self._base_station:
            base = self._base_station[0]
            base.subscribe
            return True

        return False

    @asyncio.coroutine
    def async_subscribe(self):
        """Create job to subscribe."""
        return self.hass.async_add_job(self.subscribe)

    def unsubscribe(self):
        """Unsubscribe with arlo system."""
        if self._base_station:
            base = self._base_station[0]
            base.unsubscribe
            return True

        return False

    @asyncio.coroutine
    def async_unsubscribe(self):
        """Create job to subscribe."""
        return self.hass.async_add_job(self.unsubscribe)

    def get_modes(self):
        """Get the modes."""
        if self._base_station:
            base = self._base_station[0]
            self._mode = base.mode

    @asyncio.coroutine
    def async_get_modes(self):
        """Create job to get modes."""
        return self.hass.async_add_job(self.get_modes)

    def get_cam_signal_strengths(self):
        """Get the camera signal strengths."""
        if self._base_station:
            base = self._base_station[0]
            self._camera_signal_strengths = base.get_camera_signal_strength

    @asyncio.coroutine
    def async_get_cam_signal_strengths(self):
        """Create job to get cam signal strengths."""
        return self.hass.async_add_job(self.get_cam_signal_strengths)

    def get_cam_battery_levels(self):
        """Get the camera battery levels."""
        if self._base_station:
            base = self._base_station[0]
            self._camera_battery_levels = base.get_camera_battery_level

    @asyncio.coroutine
    def async_get_cam_battery_levels(self):
        """Create job to get cam battery levels."""
        return self.hass.async_add_job(self.get_cam_battery_levels)

    def get_motion_status(self):
        """Get the camera motion status."""
        if self._base_station:
            base = self._base_station[0]
            self._motion_status = True if base.is_motion_detection_enabled else False

    @asyncio.coroutine
    def async_get_motion_status(self):
        """Create job to get motion status."""
        return self.hass.async_add_job(self.get_motion_status)

    def get_camera_properties(self):
        """Get the camera properties."""
        if self._base_station:
            base = self._base_station[0]
            self._camera_properties = base.get_camera_properties

    @asyncio.coroutine
    def async_update_properties(self, *_):
        """Get the latest data from arlo camera."""
        ret = yield from self.async_subscribe()

        yield from self.async_get_modes()
        yield from self.async_get_cam_battery_levels()
        yield from self.async_get_motion_status()
        yield from self.async_get_cam_signal_strengths()

        ret = yield from self.async_unsubscribe()

@asyncio.coroutine
def async_setup(hass, config):
    """Set up an Arlo component."""
    arlodata = ArloData(hass, config)
    hass.data[PROPS_ARLO] = arlodata

    async_track_time_interval(
        hass, arlodata.async_update_properties, timedelta(seconds=15))

    return True

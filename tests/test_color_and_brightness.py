import datetime as dt
import zoneinfo

import pytest
from astral import LocationInfo
from astral.location import Location
from homeassistant.components.adaptive_lighting.color_and_brightness import (
    SUN_EVENT_NOON,
    SUN_EVENT_SUNRISE,
    DimToWarmSettings,
    LightCapabilities,
    SunEvents,
    adjust_color_temp_for_brightness,
)

# Create a mock astral_location object
location = Location(LocationInfo())

LAT_LONG_TZS = [
    (52.379189, 4.899431, "Europe/Amsterdam"),
    (32.87336, -117.22743, "US/Pacific"),
    (60, 50, "GMT"),
    (60, 50, "UTC"),
]


@pytest.fixture(params=LAT_LONG_TZS)
def tzinfo_and_location(request):
    lat, long, timezone = request.param
    tzinfo = zoneinfo.ZoneInfo(timezone)
    location = Location(
        LocationInfo(
            name="name",
            region="region",
            timezone=timezone,
            latitude=lat,
            longitude=long,
        ),
    )
    return tzinfo, location


def test_replace_time(tzinfo_and_location):
    tzinfo, location = tzinfo_and_location
    sun_events = SunEvents(
        name="test",
        astral_location=location,
        sunrise_time=None,
        min_sunrise_time=None,
        max_sunrise_time=None,
        sunset_time=None,
        min_sunset_time=None,
        max_sunset_time=None,
        timezone=tzinfo,
    )

    new_time = dt.time(5, 30)
    datetime = dt.datetime(2022, 1, 1)
    replaced_time_utc = sun_events._replace_time(datetime.date(), new_time)
    assert replaced_time_utc.astimezone(tzinfo).time() == new_time


def test_sunrise_without_offset(tzinfo_and_location):
    tzinfo, location = tzinfo_and_location

    sun_events = SunEvents(
        name="test",
        astral_location=location,
        sunrise_time=None,
        min_sunrise_time=None,
        max_sunrise_time=None,
        sunset_time=None,
        min_sunset_time=None,
        max_sunset_time=None,
        timezone=tzinfo,
    )
    date = dt.datetime(2022, 1, 1).date()
    result = sun_events.sunrise(date)
    assert result == location.sunrise(date)


def test_sun_position_no_fixed_sunset_and_sunrise(tzinfo_and_location):
    tzinfo, location = tzinfo_and_location
    sun_events = SunEvents(
        name="test",
        astral_location=location,
        sunrise_time=None,
        min_sunrise_time=None,
        max_sunrise_time=None,
        sunset_time=None,
        min_sunset_time=None,
        max_sunset_time=None,
        timezone=tzinfo,
    )
    date = dt.datetime(2022, 1, 1).date()
    sunset = location.sunset(date)
    position = sun_events.sun_position(sunset)
    assert position == 0
    sunrise = location.sunrise(date)
    position = sun_events.sun_position(sunrise)
    assert position == 0
    noon = location.noon(date)
    position = sun_events.sun_position(noon)
    assert position == 1
    midnight = location.midnight(date)
    position = sun_events.sun_position(midnight)
    assert position == -1


def test_sun_position_fixed_sunset_and_sunrise(tzinfo_and_location):
    tzinfo, location = tzinfo_and_location
    sun_events = SunEvents(
        name="test",
        astral_location=location,
        sunrise_time=dt.time(6, 0),
        min_sunrise_time=None,
        max_sunrise_time=None,
        sunset_time=dt.time(18, 0),
        min_sunset_time=None,
        max_sunset_time=None,
        timezone=tzinfo,
    )
    date = dt.datetime(2022, 1, 1).date()
    sunset = sun_events.sunset(date)
    position = sun_events.sun_position(sunset)
    assert position == 0
    sunrise = sun_events.sunrise(date)
    position = sun_events.sun_position(sunrise)
    assert position == 0
    noon, midnight = sun_events.noon_and_midnight(date)
    position = sun_events.sun_position(noon)
    assert position == 1
    position = sun_events.sun_position(midnight)
    assert position == -1


def test_noon_and_midnight(tzinfo_and_location):
    tzinfo, location = tzinfo_and_location
    sun_events = SunEvents(
        name="test",
        astral_location=location,
        sunrise_time=None,
        min_sunrise_time=None,
        max_sunrise_time=None,
        sunset_time=None,
        min_sunset_time=None,
        max_sunset_time=None,
        timezone=tzinfo,
    )
    date = dt.datetime(2022, 1, 1)
    noon, midnight = sun_events.noon_and_midnight(date)
    assert noon == location.noon(date)
    assert midnight == location.midnight(date)


def test_sun_events(tzinfo_and_location):
    tzinfo, location = tzinfo_and_location
    sun_events = SunEvents(
        name="test",
        astral_location=location,
        sunrise_time=None,
        min_sunrise_time=None,
        max_sunrise_time=None,
        sunset_time=None,
        min_sunset_time=None,
        max_sunset_time=None,
        timezone=tzinfo,
    )

    date = dt.datetime(2022, 1, 1)
    events = sun_events.sun_events(date)
    assert len(events) == 4
    assert (SUN_EVENT_SUNRISE, location.sunrise(date).timestamp()) in events


def test_prev_and_next_events(tzinfo_and_location):
    tzinfo, location = tzinfo_and_location
    sun_events = SunEvents(
        name="test",
        astral_location=location,
        sunrise_time=None,
        min_sunrise_time=None,
        max_sunrise_time=None,
        sunset_time=None,
        min_sunset_time=None,
        max_sunset_time=None,
        timezone=tzinfo,
    )
    datetime = dt.datetime(2022, 1, 1, 10, 0)
    after_sunrise = sun_events.sunrise(datetime.date()) + dt.timedelta(hours=1)
    prev_event, next_event = sun_events.prev_and_next_events(after_sunrise)
    assert prev_event[0] == SUN_EVENT_SUNRISE
    assert next_event[0] == SUN_EVENT_NOON


def test_closest_event(tzinfo_and_location):
    tzinfo, location = tzinfo_and_location
    sun_events = SunEvents(
        name="test",
        astral_location=location,
        sunrise_time=None,
        min_sunrise_time=None,
        max_sunrise_time=None,
        sunset_time=None,
        min_sunset_time=None,
        max_sunset_time=None,
        timezone=tzinfo,
    )
    datetime = dt.datetime(2022, 1, 1, 6, 0)
    sunrise = sun_events.sunrise(datetime.date())
    event_name, ts = sun_events.closest_event(sunrise)
    assert event_name == SUN_EVENT_SUNRISE
    assert ts == location.sunrise(sunrise.date()).timestamp()


def _dim_to_warm_config(**overrides):
    return DimToWarmSettings(
        enabled=True,
        min_brightness=20,
        max_brightness=80,
        target_color_temp_mired=500,
        min_color_temp_kelvin=2000,
        max_color_temp_kelvin=5500,
        **overrides,
    )


def test_adjust_color_temp_for_brightness_disabled():
    settings = _dim_to_warm_config(enabled=False)
    capabilities = LightCapabilities(min_mireds=150, max_mireds=500)
    result = adjust_color_temp_for_brightness(250, 10, settings, capabilities)
    assert result == 250


def test_adjust_color_temp_for_brightness_full_warm():
    settings = _dim_to_warm_config()
    capabilities = LightCapabilities(min_mireds=150, max_mireds=500)
    result = adjust_color_temp_for_brightness(300, 10, settings, capabilities)
    assert result == 500


def test_adjust_color_temp_for_brightness_full_base():
    settings = _dim_to_warm_config()
    capabilities = LightCapabilities(min_mireds=150, max_mireds=500)
    result = adjust_color_temp_for_brightness(300, 90, settings, capabilities)
    assert result == 300


def test_adjust_color_temp_for_brightness_interpolated():
    settings = _dim_to_warm_config()
    capabilities = LightCapabilities(min_mireds=150, max_mireds=500)
    result = adjust_color_temp_for_brightness(200, 50, settings, capabilities)
    assert 200 < result < 500
    assert pytest.approx(350, rel=0.01) == result


def test_adjust_color_temp_for_brightness_clamped_to_capabilities():
    settings = _dim_to_warm_config(target_color_temp_mired=800)
    capabilities = LightCapabilities(min_mireds=160, max_mireds=400)
    result = adjust_color_temp_for_brightness(100, 0, settings, capabilities)
    assert result == 400


def test_adjust_color_temp_for_brightness_clamped_to_config_limits():
    settings = _dim_to_warm_config(target_color_temp_mired=None)
    capabilities = LightCapabilities(min_mireds=140, max_mireds=800)
    # Config limits allow up to 500 mireds
    result = adjust_color_temp_for_brightness(450, 0, settings, capabilities)
    assert result == 500

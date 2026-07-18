from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from adhanpy.PrayerTimes import PrayerTimes
from adhanpy.calculation.CalculationMethod import CalculationMethod
from adhanpy.calculation.CalculationParameters import CalculationParameters
from adhanpy.calculation.HighLatitudeRule import HighLatitudeRule
from adhanpy.calculation.Madhab import Madhab as AdhanMadhab

from adhan.config import LocationConfig, Madhab, OfflineConfig
from adhan.models import PrayerSchedule

# NOTE: adhanpy 1.0.5's CalculationMethod enum does not define TEHRAN or TURKEY
# (unlike some other adhan ports/versions). It defines UOIF instead. Methods
# not supported by this adhanpy version are simply omitted here, which means
# OfflineProvider will raise ValueError for them (see __init__ below) rather
# than failing at import time with AttributeError.
_METHOD_MAP = {
    "muslim_world_league": CalculationMethod.MUSLIM_WORLD_LEAGUE,
    "egyptian": CalculationMethod.EGYPTIAN,
    "karachi": CalculationMethod.KARACHI,
    "umm_al_qura": CalculationMethod.UMM_AL_QURA,
    "dubai": CalculationMethod.DUBAI,
    "moonsighting_committee": CalculationMethod.MOON_SIGHTING_COMMITTEE,
    "north_america": CalculationMethod.NORTH_AMERICA,
    "kuwait": CalculationMethod.KUWAIT,
    "qatar": CalculationMethod.QATAR,
    "singapore": CalculationMethod.SINGAPORE,
    "uoif": CalculationMethod.UOIF,
}

_HLR_MAP = {
    "middle_of_the_night": HighLatitudeRule.MIDDLE_OF_THE_NIGHT,
    "seventh_of_the_night": HighLatitudeRule.SEVENTH_OF_THE_NIGHT,
    "twilight_angle": HighLatitudeRule.TWILIGHT_ANGLE,
}


class OfflineProvider:
    def __init__(self, offline: OfflineConfig, location: LocationConfig):
        if offline.method not in _METHOD_MAP:
            raise ValueError(f"Unknown calculation method: {offline.method}")
        if offline.high_latitude_rule not in _HLR_MAP:
            raise ValueError(f"Unknown high_latitude_rule: {offline.high_latitude_rule}")
        self._offline = offline
        self._location = location
        self._tz = ZoneInfo(location.timezone)

    def get_schedule(self, day: date) -> PrayerSchedule:
        params = CalculationParameters(method=_METHOD_MAP[self._offline.method])
        params.madhab = (
            AdhanMadhab.HANAFI if self._offline.madhab is Madhab.HANAFI else AdhanMadhab.SHAFI
        )
        params.high_latitude_rule = _HLR_MAP[self._offline.high_latitude_rule]

        pt = PrayerTimes(
            (self._location.latitude, self._location.longitude),
            day,
            calculation_parameters=params,
            time_zone=self._tz,
        )
        return PrayerSchedule(
            fajr=pt.fajr, sunrise=pt.sunrise, dhuhr=pt.dhuhr,
            asr=pt.asr, maghrib=pt.maghrib, isha=pt.isha,
        )

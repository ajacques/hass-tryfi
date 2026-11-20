import datetime
import logging
import requests
from .common import query
from .const import PET_ACTIVITY_ONGOINGWALK
from .fiDevice import FiDevice
from .common.response_handlers import parse_fi_date
from .exceptions import ApiNotAuthorizedError

LOGGER = logging.getLogger(__name__)

# A collar can be permanently refused health trends while the rest of the
# account works (TryFi answers 200 with a GraphQL "Unauthorized"). Retrying it
# every poll costs three calls per cycle indefinitely, so stop asking that
# collar after repeated refusals and try again later. State is per pet, so a
# refusal for one never suppresses another.
BEHAVIOR_AUTH_FAILURE_LIMIT = 3
BEHAVIOR_AUTH_BACKOFF = datetime.timedelta(minutes=30)

# Behavior trend periods as returned by the API, mapped to the prefix used in
# the public (legacy) attribute names, e.g. dailyBarkingCount.
BEHAVIOR_PERIODS = {"DAY": "daily", "WEEK": "weekly", "MONTH": "monthly"}

# Names of the tracked behaviors (also used for the public attribute names).
BEHAVIORS = ("barking", "licking", "scratching", "eating", "drinking")


class FiPet(object):
    def __init__(self, petId):
        self._petId = petId
        self._behaviorAuthFailures = 0
        self._behaviorAuthRetryAt = None
        self._name = None
        self._yearOfBirth = None
        self._monthOfBirth = None
        self._gender = None
        self._currPlaceName = None
        self._currPlaceAddress = None
        self._device = None
        self._secondaryDevice = None
        self._weight = None
        self._lastUpdated = None
        self._locationLastUpdate = None
        self._posAccuracy = None

        # Behavior metrics (Series 3+ only), keyed by period and behavior name:
        # self._behaviorStats["daily"]["barking"]["count"] -> int
        # self._behaviorStats["daily"]["barking"]["duration"] -> minutes
        # Values start as None ("unknown") until the collar reports them.
        self._behaviorStats = {
            period: {
                behavior: {"count": None, "duration": None} for behavior in BEHAVIORS
            }
            for period in BEHAVIOR_PERIODS
        }

    def _behaviorValue(self, period: str, behavior: str, metric: str) -> int | None:
        """Return one behavior metric, or None when it is unknown/unsupported.

        Some collars never report certain behaviors (their trend has no
        ``eventsSummary``), so those metrics are deliberately left unset and
        must not be reported as zero.
        """
        return self._behaviorStats.get(period, {}).get(behavior, {}).get(metric)

    def setPetDetailsJSON(self, petJSON: dict):
        self._name = petJSON.get("name")
        self._yearOfBirth = petJSON["yearOfBirth"]
        self._monthOfBirth = int(petJSON["monthOfBirth"])
        self._dayOfBirth = int(petJSON["dayOfBirth"])
        self._gender = petJSON.get("gender")
        self._weight = float(petJSON["weight"]) if "weight" in petJSON else None
        self._breed = petJSON["breed"].get("name") if "breed" in petJSON else None
        try:
            self._photoLink = petJSON["photos"]["first"]["image"]["fullSize"]
        except Exception:
            LOGGER.warning("Cannot find photo of your pet. Defaulting to empty string.")
            self._photoLink = ""
        self._device = FiDevice(petJSON["device"]["id"])
        self._device.setDeviceDetailsJSON(petJSON["device"])

        secondaryDeviceJSON = petJSON.get("secondaryDevice")
        if secondaryDeviceJSON:
            self._secondaryDevice = FiDevice(secondaryDeviceJSON.get("id"))
            self._secondaryDevice.setDeviceDetailsJSON(secondaryDeviceJSON)
        else:
            self._secondaryDevice = None

        self._lastUpdated = datetime.datetime.now()

    def __str__(self):
        return f"Last Updated - {self.lastUpdated} - Pet ID: {self.petId} Name: {self.name} Is Lost: {self.isLost} ActivityType: {self.activityType} Located: {self.currLatitude},{self.currLongitude} Last Updated: {self.currStartTime}\n \
            using Device/Collar: {self._device}"

    # set the Pet's current location details
    def setCurrentLocation(self, activityJSON):
        activityType = activityJSON["__typename"]
        self._activityType = activityType
        self._areaName = activityJSON["areaName"]
        self._locationLastUpdate = parse_fi_date(activityJSON["lastReportTimestamp"])
        if activityType == PET_ACTIVITY_ONGOINGWALK:
            currentLocation = activityJSON["positions"][-1]
            self._posAccuracy = (
                currentLocation["errorRadius"]
                if "errorRadius" in currentLocation
                else None
            )
            currentPosition = currentLocation["position"]
        else:  # OngoingRest
            currentPosition = activityJSON["position"]
            if "place" in activityJSON and activityJSON["place"] is not None:
                self._posAccuracy = activityJSON["place"]["radius"]
            else:
                self._posAccuracy = 0

        self._currLongitude = currentPosition["longitude"]
        self._currLatitude = currentPosition["latitude"]
        self._currStartTime = datetime.datetime.fromisoformat(
            activityJSON["start"].replace("Z", "+00:00")
        )

        if "place" in activityJSON and activityJSON["place"] is not None:
            self._currPlaceName = activityJSON["place"]["name"]
            self._currPlaceAddress = activityJSON["place"]["address"]
        else:
            self._currPlaceName = None
            self._currPlaceAddress = None
        self._lastUpdated = datetime.datetime.now()

    # set the Pet's current steps, goals and distance details for daily, weekly and monthly
    def setStats(self, activityJSONDaily, activityJSONWeekly, activityJSONMonthly):
        # distance is in metres
        def summary_values(stepObject):
            if not stepObject:
                return None, None, None
            summary = stepObject.get("stepSummary") or {}
            goal = summary.get("stepGoal")
            steps = summary.get("totalSteps")
            distance = summary.get("totalWalkDistanceMeters")
            return (
                int(goal) if goal is not None else None,
                int(steps) if steps is not None else None,
                float(distance) if distance is not None else None,
            )

        (
            self._dailyGoal,
            self._dailySteps,
            self._dailyTotalDistance,
        ) = summary_values(activityJSONDaily)
        if activityJSONWeekly:
            (
                self._weeklyGoal,
                self._weeklySteps,
                self._weeklyTotalDistance,
            ) = summary_values(activityJSONWeekly)
        if activityJSONMonthly:
            (
                self._monthlyGoal,
                self._monthlySteps,
                self._monthlyTotalDistance,
            ) = summary_values(activityJSONMonthly)

        self._lastUpdated = datetime.datetime.now()

    # Update the Stats of the pet
    def updateStats(self, sessionId: requests.Session):
        try:
            pStatsJSON = query.getCurrentPetStats(sessionId, self.petId)
            self.setStats(
                pStatsJSON["dailyStat"],
                pStatsJSON["weeklyStat"],
                pStatsJSON["monthlyStat"],
            )
            return True
        except Exception as e:
            LOGGER.error(f"Could not update stats for Pet {self.name}.\n{e}")
            return False

    def _extractSleep(self, restObject: dict | None) -> tuple[int | None, int | None]:
        if restObject is None:
            return None, None
        restSummary = restObject.get("restSummary")
        if not restSummary:
            LOGGER.warning(
                f"Can't extract sleep because restSummary is missing: {restObject}"
            )
            return None, None
        sleep = restSummary.get("sleepSecondsTotal")
        nap = restSummary.get("napSecondsTotal")
        sleep = int(sleep) if sleep is not None else 0
        nap = int(nap) if nap is not None else 0
        return sleep, nap

    # Update the Stats of the pet
    def updateRestStats(self, sessionId: requests.Session):
        pRestStatsJSON = None
        try:
            pRestStatsJSON = query.getCurrentPetRestStats(sessionId, self.petId)
            self._dailySleep, self._dailyNap = self._extractSleep(
                pRestStatsJSON["dailyStat"]
            )
            self._weeklySleep, self._weeklyNap = self._extractSleep(
                pRestStatsJSON["weeklyStat"]
            )
            self._monthlySleep, self._monthlyNap = self._extractSleep(
                pRestStatsJSON["monthlyStat"]
            )
            return True
        except Exception as e:
            LOGGER.error(
                f"Could not update rest stats for Pet {self.name}\n{pRestStatsJSON}.\n{e}",
                exc_info=True,
            )
            return False

    # Update the Pet's GPS location
    def updatePetLocation(self, sessionId: requests.Session):
        try:
            pLocJSON = query.getCurrentPetLocation(sessionId, self.petId)
            self.setCurrentLocation(pLocJSON)
            return True
        except Exception as e:
            LOGGER.error(f"Could not update Pet: {self.name}'s location.\n{e}")
            return False

    # Update the device/collar details for this pet
    def updateDeviceDetails(self, sessionId: requests.Session):
        try:
            deviceJSON = query.getDevicedetails(sessionId, self.petId)
            self.device.setDeviceDetailsJSON(deviceJSON["device"])
            return True
        except Exception as e:
            LOGGER.error(
                f"Could not update Device/Collar information for Pet: {self.name}\n{e}"
            )
            return False

    # Update all details regarding this pet
    def updateAllDetails(self, session: requests.Session):
        petJson = query.getPetAllInfo(session, self.petId)
        self.device.setDeviceDetailsJSON(petJson["device"])
        secondaryDeviceJSON = petJson.get("secondaryDevice")
        if secondaryDeviceJSON:
            if self._secondaryDevice is None:
                self._secondaryDevice = FiDevice(secondaryDeviceJSON.get("id"))
            self._secondaryDevice.setDeviceDetailsJSON(secondaryDeviceJSON)
        else:
            self._secondaryDevice = None
        self.setCurrentLocation(petJson["ongoingActivity"])
        self.setStats(
            petJson["dailyStepStat"],
            petJson["weeklyStepStat"],
            petJson["monthlyStepStat"],
        )
        self._dailySleep, self._dailyNap = self._extractSleep(petJson["dailySleepStat"])
        self._weeklySleep, self._weeklyNap = self._extractSleep(
            petJson["weeklySleepStat"]
        )
        self._monthlySleep, self._monthlyNap = self._extractSleep(
            petJson["monthlySleepStat"]
        )

        if self.device.supportsAdvancedBehaviorStats():
            # Try to fetch behavior data for Series 3+ collars
            try:
                self.updateBehaviorStats(session)
            except Exception as e:
                LOGGER.warning(
                    f"Could not update behavior stats for Pet {self.name}.\n{e}"
                )
                # Behavior stats may not be available for older collars
                pass

    # Update behavior stats for Series 3+ collars
    def updateBehaviorStats(self, sessionId: requests.Session):
        """Update behavior statistics for Series 3+ collars."""
        now = datetime.datetime.now(datetime.timezone.utc)
        if self._behaviorAuthRetryAt is not None and now < self._behaviorAuthRetryAt:
            return
        for period in ["DAY", "WEEK", "MONTH"]:
            try:
                healthTrendsJSON = query.getPetHealthTrends(
                    sessionId, self.petId, period
                )
                behavior_trends = healthTrendsJSON.get("behaviorTrends", [])
                self.setBehaviorStatsFromTrends(behavior_trends, period)
                self._behaviorAuthFailures = 0
                self._behaviorAuthRetryAt = None
            except ApiNotAuthorizedError as e:
                # The refusal is per collar, not per period, so the remaining
                # periods fail identically; ask once per cycle, not three times.
                self._behaviorAuthFailures += 1
                if self._behaviorAuthFailures >= BEHAVIOR_AUTH_FAILURE_LIMIT:
                    self._behaviorAuthRetryAt = now + BEHAVIOR_AUTH_BACKOFF
                    LOGGER.warning(
                        f"Behavior trends for {self.name} refused "
                        f"{self._behaviorAuthFailures} times in a row: {e}. "
                        f"Not asking again for {BEHAVIOR_AUTH_BACKOFF}."
                    )
                else:
                    LOGGER.warning(
                        f"Could not fetch {period} behavior trends for {self.name}: {e}"
                    )
                return
            except Exception as e:
                LOGGER.warning(
                    f"Could not fetch {period} behavior trends for {self.name}: {e}"
                )

    def _parseBehaviorDuration(self, input: str) -> int:
        # examples: '1hr 5min', '46min', '1.5hr', '<1min', '10.1'
        if input.startswith("<"):
            return 0
        elif "hr " in input and "min" in input:
            parts = input.split()
            hours = 0
            minutes = 0
            for part in parts:
                if part.endswith("hr"):
                    hours = float(part.replace("hr", ""))
                elif part.endswith("min"):
                    minutes = float(part.replace("min", ""))
            return round(hours * 60 + minutes)
        elif input.endswith("min"):
            return round(float(input.replace("min", "")))
        elif input.endswith("hr"):
            return round(float(input.replace("hr", "")) * 60)
        else:
            return round(float(input))

    def setBehaviorStatsFromTrends(self, behaviorTrends, period: str = "DAY"):
        """Parse behavior data from health trends API."""
        period = period if period in BEHAVIOR_PERIODS else "DAY"

        # Map from API trend title to our behavior name. The API no longer
        # exposes a stable `id` on health trends (v3.128.0); the human-readable
        # `title` is the only identifier returned.
        TITLE_MAP = {
            "barking": "barking",
            "licking": "licking",
            "cleaning_self": "licking",
            "scratching": "scratching",
            "eating": "eating",
            "drinking": "drinking",
        }

        # Reset every metric for this period to "unknown" (None). Behaviors the
        # collar does not report stay None rather than being reported as zero.
        periodStats = {
            behavior: {"count": None, "duration": None} for behavior in BEHAVIORS
        }

        for trend in behaviorTrends or []:
            if not isinstance(trend, dict):
                LOGGER.warning(
                    f"Found non-dict item ('{type(trend)}') in behaviorTrends. Skipping."
                )
                continue

            title = trend.get("title", "")
            summary = trend.get("summaryComponents") or {}

            # Extract events count
            events_summary = summary.get("eventsSummary")
            if events_summary is None:
                # This will be None when the collar doesn't support the stat
                continue
            events_count = 0
            if events_summary:
                events_count = round(float(events_summary.split()[0]))

            # Extract duration
            duration_summary = summary.get("durationSummary")
            duration_minutes = 0
            if duration_summary:
                duration_minutes = self._parseBehaviorDuration(duration_summary)

            # Identify the behavior by its title (e.g. "Barking" -> "barking")
            behavior = TITLE_MAP.get(title.strip().lower())
            if behavior:
                periodStats[behavior] = {
                    "count": events_count,
                    "duration": duration_minutes,
                }

        self._behaviorStats[BEHAVIOR_PERIODS[period]] = periodStats

    def setWeight(self, session: requests.Session, weight_kg: float):
        try:
            updated_weight = query.updatePetWeight(session, self.petId, weight_kg)
            self._weight = float(updated_weight)
            return True
        except Exception as e:
            LOGGER.error(f"Could not update weight for Pet {self.name}.\n{e}")
            return False

    # set the color code of the led light on the pet collar
    def setLedColorCode(self, session: requests.Session, colorCode):
        try:
            moduleId = self.device.moduleId
            ledColorCode = int(colorCode)
            setColorJSON = query.setLedColor(session, moduleId, ledColorCode)
            try:
                self.device.setDeviceDetailsJSON(setColorJSON["setDeviceLed"])
            except Exception as e:
                LOGGER.warning(
                    f"Updated LED Color but could not get current status for Pet: {self.name}\nException: {e}"
                )
            return True
        except Exception as e:
            LOGGER.error(f"Could not complete Led Color request:\n{e}")
            return False

    # turn on or off the led light. action = True will enable the light, false turns off the light
    def turnOnOffLed(self, sessionId, action):
        try:
            moduleId = self.device.moduleId
            onOffResponse = query.turnOnOffLed(sessionId, moduleId, action)
            try:
                self.device.setDeviceDetailsJSON(
                    onOffResponse["updateDeviceOperationParams"]
                )
            except Exception:
                LOGGER.warning(
                    f"Action: {action} was successful however unable to get current status for Pet: {self.name}"
                )
            return True
        except Exception as e:
            LOGGER.error(f"Could not complete LED request:\n{e}")
            return False

    # set the lost dog mode to Normal or Lost Dog. Action is true for lost dog and false for normal (not lost)
    def setLostDogMode(self, sessionId, action):
        try:
            moduleId = self.device.moduleId
            petModeResponse = query.setLostDogMode(sessionId, moduleId, action)
            try:
                self.device.setDeviceDetailsJSON(
                    petModeResponse["updateDeviceOperationParams"]
                )
            except Exception:
                LOGGER.warning(
                    f"Action: {action} was successful however unable to get current status for Pet: {self.name}"
                )
            return True
        except Exception as e:
            LOGGER.error(
                f"Could not complete turn on/off light where ledEnable is {action}.\nException: {e}"
            )
            return False

    @property
    def device(self):
        return self._device

    @property
    def secondaryDevice(self):
        return self._secondaryDevice

    @property
    def petId(self):
        return self._petId

    @property
    def name(self):
        return self._name

    @property
    def yearOfBirth(self):
        return self._yearOfBirth

    @property
    def monthOfBirth(self):
        return self._monthOfBirth

    @property
    def dayOfBirth(self):
        return self._dayOfBirth

    @property
    def gender(self):
        return self._gender

    @property
    def weight(self):
        return self._weight

    @property
    def breed(self):
        return self._breed

    @property
    def photoLink(self) -> str | None:
        return self._photoLink

    @property
    def currLongitude(self) -> float | None:
        return self._currLongitude

    @property
    def currLatitude(self) -> float | None:
        return self._currLatitude

    @property
    def positionAccuracy(self) -> float | None:
        return self._posAccuracy

    @property
    def currStartTime(self):
        return self._currStartTime

    @property
    def currPlaceName(self):
        return self._currPlaceName

    @property
    def currPlaceAddress(self):
        return self._currPlaceAddress

    @property
    def dailyGoal(self):
        return self._dailyGoal

    @property
    def dailySteps(self):
        return self._dailySteps

    @property
    def dailyTotalDistance(self):
        return self._dailyTotalDistance

    @property
    def weeklyGoal(self):
        return self._weeklyGoal

    @property
    def weeklySteps(self):
        return self._weeklySteps

    @property
    def weeklyTotalDistance(self):
        return self._weeklyTotalDistance

    @property
    def monthlyGoal(self):
        return self._monthlyGoal

    @property
    def monthlySteps(self):
        return self._monthlySteps

    @property
    def monthlyTotalDistance(self):
        return self._monthlyTotalDistance

    @property
    def dailySleep(self):
        return self._dailySleep

    @property
    def weeklySleep(self):
        return self._weeklySleep

    @property
    def monthlySleep(self):
        return self._monthlySleep

    @property
    def dailyNap(self):
        return self._dailyNap

    @property
    def weeklyNap(self):
        return self._weeklyNap

    @property
    def monthlyNap(self):
        return self._monthlyNap

    @property
    def locationLastUpdate(self):
        return self._locationLastUpdate

    @property
    def locationNextEstimatedUpdate(self):
        return self._device._nextLocationUpdatedExpectedBy

    @property
    def lastUpdated(self):
        return self._lastUpdated

    @property
    def isLost(self):
        return self.device.isLost

    @property
    def activityType(self):
        return self._activityType

    @property
    def areaName(self):
        return self._areaName

    @property
    def signalStrength(self):
        return self._connectionSignalStrength

    def getCurrPlaceName(self):
        return self.currPlaceName

    def getCurrPlaceAddress(self):
        return self.currPlaceAddress

    def getActivityType(self):
        return self.activityType

    def getBirthDate(self):
        return datetime.datetime(self.yearOfBirth, self.monthOfBirth, self.dayOfBirth)

    def getDailySteps(self):
        return self.dailySteps

    def getDailyGoal(self):
        return self.dailyGoal

    def getDailyDistance(self):
        return self.dailyTotalDistance

    def getWeeklySteps(self):
        return self.weeklySteps

    def getWeeklyGoal(self):
        return self.weeklyGoal

    def getWeeklyDistance(self):
        return self.weeklyTotalDistance

    def getMonthlySteps(self):
        return self.monthlySteps

    def getMonthlyGoal(self):
        return self.monthlyGoal

    def getMonthlyDistance(self):
        return self.monthlyTotalDistance

    # Behavior properties (Series 3+ only). Each returns None while the
    # value is unknown, e.g. when the collar does not report that behavior.
    # Barking
    @property
    def dailyBarkingCount(self) -> int | None:
        return self._behaviorValue("daily", "barking", "count")

    @property
    def weeklyBarkingCount(self) -> int | None:
        return self._behaviorValue("weekly", "barking", "count")

    @property
    def monthlyBarkingCount(self) -> int | None:
        return self._behaviorValue("monthly", "barking", "count")

    @property
    def dailyBarkingDuration(self) -> int | None:
        return self._behaviorValue("daily", "barking", "duration")

    @property
    def weeklyBarkingDuration(self) -> int | None:
        return self._behaviorValue("weekly", "barking", "duration")

    @property
    def monthlyBarkingDuration(self) -> int | None:
        return self._behaviorValue("monthly", "barking", "duration")

    # Licking
    @property
    def dailyLickingCount(self) -> int | None:
        return self._behaviorValue("daily", "licking", "count")

    @property
    def weeklyLickingCount(self) -> int | None:
        return self._behaviorValue("weekly", "licking", "count")

    @property
    def monthlyLickingCount(self) -> int | None:
        return self._behaviorValue("monthly", "licking", "count")

    @property
    def dailyLickingDuration(self) -> int | None:
        return self._behaviorValue("daily", "licking", "duration")

    @property
    def weeklyLickingDuration(self) -> int | None:
        return self._behaviorValue("weekly", "licking", "duration")

    @property
    def monthlyLickingDuration(self) -> int | None:
        return self._behaviorValue("monthly", "licking", "duration")

    # Scratching
    @property
    def dailyScratchingCount(self) -> int | None:
        return self._behaviorValue("daily", "scratching", "count")

    @property
    def weeklyScratchingCount(self) -> int | None:
        return self._behaviorValue("weekly", "scratching", "count")

    @property
    def monthlyScratchingCount(self) -> int | None:
        return self._behaviorValue("monthly", "scratching", "count")

    @property
    def dailyScratchingDuration(self) -> int | None:
        return self._behaviorValue("daily", "scratching", "duration")

    @property
    def weeklyScratchingDuration(self) -> int | None:
        return self._behaviorValue("weekly", "scratching", "duration")

    @property
    def monthlyScratchingDuration(self) -> int | None:
        return self._behaviorValue("monthly", "scratching", "duration")

    # Eating
    @property
    def dailyEatingCount(self) -> int | None:
        return self._behaviorValue("daily", "eating", "count")

    @property
    def weeklyEatingCount(self) -> int | None:
        return self._behaviorValue("weekly", "eating", "count")

    @property
    def monthlyEatingCount(self) -> int | None:
        return self._behaviorValue("monthly", "eating", "count")

    @property
    def dailyEatingDuration(self) -> int | None:
        return self._behaviorValue("daily", "eating", "duration")

    @property
    def weeklyEatingDuration(self) -> int | None:
        return self._behaviorValue("weekly", "eating", "duration")

    @property
    def monthlyEatingDuration(self) -> int | None:
        return self._behaviorValue("monthly", "eating", "duration")

    # Drinking
    @property
    def dailyDrinkingCount(self) -> int | None:
        return self._behaviorValue("daily", "drinking", "count")

    @property
    def weeklyDrinkingCount(self) -> int | None:
        return self._behaviorValue("weekly", "drinking", "count")

    @property
    def monthlyDrinkingCount(self) -> int | None:
        return self._behaviorValue("monthly", "drinking", "count")

    @property
    def dailyDrinkingDuration(self) -> int | None:
        return self._behaviorValue("daily", "drinking", "duration")

    @property
    def weeklyDrinkingDuration(self) -> int | None:
        return self._behaviorValue("weekly", "drinking", "duration")

    @property
    def monthlyDrinkingDuration(self) -> int | None:
        return self._behaviorValue("monthly", "drinking", "duration")

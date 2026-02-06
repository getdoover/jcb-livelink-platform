"""
JCB LiveLink Platform Processor

Periodically polls the JCB LiveLink API to retrieve machine telematics data
(location, fuel, hours, alerts, utilisation) and publishes it to the Doover
tag system for display on the platform.
"""

import json
import logging
import re
from datetime import datetime, timezone

import httpx

from pydoover.cloud.processor import ProcessorBase

log = logging.getLogger(__name__)


class JcbLivelinkPlatformProcessor(ProcessorBase):
    """Doover processor that polls the JCB LiveLink API for machine telematics data."""

    def setup(self):
        """Initialize HTTP client and load configuration from deployment config."""
        log.info("Setting up JCB LiveLink Platform processor")

        # Load config from deployment (package) config
        self.base_url = (
            self.get_agent_config("api_base_url") or "https://api.jcblivelink.com"
        ).rstrip("/")
        self.api_token = self.get_agent_config("api_token") or ""
        self.poll_interval = self.get_agent_config("poll_interval_minutes") or 15

        # Machine selection
        self.configured_machine_ids = self.get_agent_config("machine_ids") or []

        # Data inclusion toggles (default True)
        self.inc_location = self._config_bool("include_location", True)
        self.inc_fuel = self._config_bool("include_fuel", True)
        self.inc_hours = self._config_bool("include_hours", True)
        self.inc_alerts = self._config_bool("include_alerts", True)
        self.inc_utilisation = self._config_bool("include_utilisation", True)

        # Build HTTP client
        self.http_client = None
        if self.api_token:
            self.http_client = httpx.Client(
                timeout=60.0,
                headers={
                    "Authorization": f"Bearer {self.api_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "User-Agent": "doover-jcb-livelink-platform/0.1.0",
                },
            )
        else:
            log.warning("API token not configured - will not be able to poll API")

    def process(self):
        """Process incoming message or scheduled trigger.

        If a message is received (e.g., a manual refresh command), handle it.
        Otherwise, treat as a scheduled invocation and poll the API.
        """
        if self.message is not None:
            data = self.message.data
            log.info("Processing incoming message")

            if isinstance(data, dict):
                command = data.get("command", "")
                if command in ("refresh", "force-refresh", "poll"):
                    log.info("Manual refresh command received, triggering poll")
                    self._poll_api()
                else:
                    log.info("Received message with no recognized command: %s", data)
            else:
                log.info("Received non-dict message, ignoring")
        else:
            # No message - scheduled invocation
            log.info("Scheduled invocation - polling JCB LiveLink API")
            self._poll_api()

    def close(self):
        """Clean up HTTP client resources."""
        if self.http_client:
            self.http_client.close()
        log.info("JCB LiveLink Platform processor closed")

    # -------------------------------------------------------------------------
    # API Polling
    # -------------------------------------------------------------------------

    def _poll_api(self):
        """Fetch machine data from JCB LiveLink API and update tags."""
        if not self.http_client:
            log.error("HTTP client not initialised - check API token configuration")
            self._set_tag("last_poll_status", "error")
            self._set_tag("last_error", "HTTP client not initialised - API token not configured")
            return

        now = datetime.now(timezone.utc)

        try:
            machines = self._fetch_machines()

            if not machines:
                log.info("No machines returned from API")
                self._set_tag("last_poll_status", "success")
                self._set_tag("last_poll_timestamp", now.isoformat())
                self._set_tag("machine_count", 0)
                self._set_tag("machines", {})
                return

            machines_summary = {}

            for machine in machines:
                machine_id = str(
                    machine.get("id", machine.get("equipmentId", ""))
                )
                if not machine_id:
                    continue

                safe_id = self._sanitize_id(machine_id)
                machine_data = self._fetch_machine_details(machine_id, machine)

                # Set per-machine tags based on config toggles
                self._set_machine_tags(safe_id, machine_data)

                # Build summary entry
                machines_summary[safe_id] = {
                    "id": machine_id,
                    "name": machine_data.get("info", {}).get("name", ""),
                    "model": machine_data.get("info", {}).get("model", ""),
                    "last_updated": now.isoformat(),
                }

            self._set_tag("machines", machines_summary)
            self._set_tag("machine_count", len(machines_summary))
            self._set_tag("last_poll_status", "success")
            self._set_tag("last_poll_timestamp", now.isoformat())
            self._set_tag("last_error", "")

            log.info("Successfully polled %d machine(s)", len(machines_summary))

        except httpx.HTTPStatusError as e:
            log.error("API HTTP error: %s %s", e.response.status_code, e.response.reason_phrase)
            status = "auth_failed" if e.response.status_code in (401, 403) else "error"
            self._set_tag("last_poll_status", status)
            self._set_tag("last_error", f"HTTP {e.response.status_code}: {e.response.reason_phrase}")

        except httpx.RequestError as e:
            log.error("API connection error: %s", str(e))
            self._set_tag("last_poll_status", "error")
            self._set_tag("last_error", f"Connection error: {str(e)}")

        except Exception as e:
            log.exception("Unexpected error during API poll")
            self._set_tag("last_poll_status", "error")
            self._set_tag("last_error", f"Unexpected error: {str(e)}")

    # -------------------------------------------------------------------------
    # API Client Methods
    # -------------------------------------------------------------------------

    def _fetch_machines(self) -> list[dict]:
        """Fetch the list of machines from the API.

        If specific machine_ids are configured, returns stubs for those IDs.
        Otherwise, fetches all available machines from the fleet endpoint.
        """
        if self.configured_machine_ids:
            return [{"id": mid} for mid in self.configured_machine_ids]

        # Try common AEMP-style fleet endpoints
        for endpoint in ("/Fleet", "/fleet", "/Equipment", "/equipment", "/machines"):
            url = f"{self.base_url}{endpoint}"
            try:
                response = self.http_client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict):
                        for key in ("equipment", "machines", "fleet", "data", "items", "results"):
                            if key in data and isinstance(data[key], list):
                                return data[key]
                        return [data]
                elif response.status_code == 404:
                    continue
                else:
                    response.raise_for_status()
            except httpx.HTTPStatusError:
                raise
            except httpx.RequestError:
                continue

        log.warning("No fleet endpoint responded successfully at %s", self.base_url)
        return []

    def _fetch_machine_details(self, machine_id: str, base_data: dict) -> dict:
        """Fetch detailed telematics data for a single machine.

        Returns a normalized dict with keys: info, location, hours, fuel, alerts, utilisation.
        """
        result = {
            "info": self._extract_info(base_data),
            "location": {},
            "hours": {},
            "fuel": {},
            "alerts": [],
            "utilisation": {},
        }

        detail_data = self._get_json(
            f"/Equipment/{machine_id}",
            fallbacks=[
                f"/equipment/{machine_id}",
                f"/machines/{machine_id}",
                f"/Fleet/{machine_id}",
            ],
        )

        source_data = {**base_data, **detail_data} if detail_data else base_data
        if detail_data:
            result["info"] = self._extract_info(source_data)

        result["location"] = self._extract_location(source_data)
        result["hours"] = self._extract_hours(source_data)
        result["fuel"] = self._extract_fuel(source_data)
        result["alerts"] = self._extract_alerts(source_data)
        result["utilisation"] = self._extract_utilisation(source_data)

        return result

    def _get_json(self, path: str, fallbacks: list[str] | None = None) -> dict | None:
        """GET a JSON endpoint, trying fallback paths on 404."""
        paths_to_try = [path] + (fallbacks or [])
        for p in paths_to_try:
            url = f"{self.base_url}{p}"
            try:
                response = self.http_client.get(url)
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    continue
                else:
                    log.warning("GET %s returned %s", url, response.status_code)
                    continue
            except httpx.RequestError as e:
                log.warning("GET %s failed: %s", url, str(e))
                continue
        return None

    # -------------------------------------------------------------------------
    # Data Extraction / Normalization
    # -------------------------------------------------------------------------

    @staticmethod
    def _extract_info(data: dict) -> dict:
        """Extract machine identity info."""
        return {
            "make": data.get("make", data.get("oem", data.get("manufacturer", "JCB"))),
            "model": data.get("model", data.get("modelName", "")),
            "serial": data.get(
                "serialNumber",
                data.get("serial", data.get("equipmentSerialNumber", "")),
            ),
            "name": data.get(
                "name",
                data.get("equipmentName", data.get("displayName", "")),
            ),
        }

    @staticmethod
    def _extract_location(data: dict) -> dict:
        """Extract GPS location data, normalizing to standard keys."""
        lat = data.get("latitude", data.get("lat", None))
        lon = data.get("longitude", data.get("lon", data.get("lng", None)))

        # Check for nested location objects
        location = data.get("location", data.get("position", data.get("gps", {})))
        if isinstance(location, dict):
            lat = lat or location.get("latitude", location.get("lat", None))
            lon = lon or location.get(
                "longitude", location.get("lon", location.get("lng", None))
            )

        if lat is None or lon is None:
            return {}

        try:
            lat = float(lat)
            lon = float(lon)
        except (ValueError, TypeError):
            return {}

        timestamp = data.get(
            "locationTimestamp",
            data.get("locationDateTime", data.get("timestamp", "")),
        )
        address = data.get("address", data.get("location_address", ""))

        return {
            "lat": lat,
            "lon": lon,
            "timestamp": _normalize_timestamp(timestamp),
            "address": address,
        }

    @staticmethod
    def _extract_hours(data: dict) -> dict:
        """Extract operating hours data."""
        total = data.get(
            "cumulativeOperatingHours",
            data.get("totalHours", data.get("engineHours", data.get("hours", None))),
        )
        idle = data.get(
            "cumulativeIdleHours",
            data.get("idleHours", data.get("idle_hours", None)),
        )

        result = {"last_updated": datetime.now(timezone.utc).isoformat()}
        if total is not None:
            try:
                result["total_hours"] = float(total)
            except (ValueError, TypeError):
                pass
        if idle is not None:
            try:
                result["idle_hours"] = float(idle)
            except (ValueError, TypeError):
                pass
        return result

    @staticmethod
    def _extract_fuel(data: dict) -> dict:
        """Extract fuel consumption data."""
        consumed = data.get(
            "fuelUsed",
            data.get("totalFuelConsumed", data.get("fuelConsumed", None)),
        )
        remaining = data.get(
            "fuelRemaining",
            data.get("fuelRemainingPercent", data.get("fuelLevel", None)),
        )
        last_24h = data.get(
            "fuelUsedLast24",
            data.get("fuelConsumedLast24h", None),
        )

        result = {"last_updated": datetime.now(timezone.utc).isoformat()}
        if consumed is not None:
            try:
                result["total_consumed"] = float(consumed)
            except (ValueError, TypeError):
                pass
        if remaining is not None:
            try:
                result["remaining_pct"] = float(remaining)
            except (ValueError, TypeError):
                pass
        if last_24h is not None:
            try:
                result["last_24h"] = float(last_24h)
            except (ValueError, TypeError):
                pass
        return result

    @staticmethod
    def _extract_alerts(data: dict) -> list:
        """Extract active alerts."""
        alerts = data.get("alerts", data.get("alarms", data.get("faults", [])))
        if isinstance(alerts, list):
            return alerts
        if isinstance(alerts, dict):
            for key in ("items", "data", "alerts"):
                if key in alerts and isinstance(alerts[key], list):
                    return alerts[key]
            return [alerts]
        return []

    @staticmethod
    def _extract_utilisation(data: dict) -> dict:
        """Extract utilisation metrics."""
        utilisation_pct = data.get(
            "utilisation",
            data.get("utilisationPercent", data.get("utilizationPercent", None)),
        )
        idle_pct = data.get(
            "idlePercent",
            data.get("idlePercentage", None),
        )

        result = {"last_updated": datetime.now(timezone.utc).isoformat()}
        if utilisation_pct is not None:
            try:
                result["utilisation_pct"] = float(utilisation_pct)
            except (ValueError, TypeError):
                pass
        if idle_pct is not None:
            try:
                result["idle_pct"] = float(idle_pct)
            except (ValueError, TypeError):
                pass
        return result

    # -------------------------------------------------------------------------
    # Tag Helpers
    # -------------------------------------------------------------------------

    def _set_tag(self, tag_name: str, value):
        """Publish a value to a tag channel (tag_values convention).

        Uses the Doover API to publish data to a named channel on this agent,
        which the platform interprets as a tag key-value pair.
        """
        try:
            self.api.publish_to_channel_name(
                self.agent_id,
                tag_name,
                value if not isinstance(value, (dict, list)) else json.dumps(value),
            )
        except Exception as e:
            log.warning("Failed to set tag '%s': %s", tag_name, str(e))

    def _get_tag(self, tag_name: str, default=None):
        """Read the current value of a tag from this agent's channels."""
        try:
            channel = self.fetch_channel_named(tag_name)
            aggregate = channel.fetch_aggregate()
            if aggregate is not None:
                return aggregate
        except Exception:
            pass
        return default

    def _set_machine_tags(self, safe_id: str, machine_data: dict):
        """Set per-machine tags based on configuration toggles."""
        # Always set machine info
        if machine_data.get("info"):
            self._set_tag(f"machine_{safe_id}_info", machine_data["info"])

        if self.inc_location and machine_data.get("location"):
            self._set_tag(f"machine_{safe_id}_location", machine_data["location"])

        if self.inc_hours and machine_data.get("hours"):
            self._set_tag(f"machine_{safe_id}_hours", machine_data["hours"])

        if self.inc_fuel and machine_data.get("fuel"):
            self._set_tag(f"machine_{safe_id}_fuel", machine_data["fuel"])

        if self.inc_alerts and machine_data.get("alerts"):
            self._set_tag(f"machine_{safe_id}_alerts", machine_data["alerts"])

        if self.inc_utilisation and machine_data.get("utilisation"):
            self._set_tag(f"machine_{safe_id}_utilisation", machine_data["utilisation"])

    # -------------------------------------------------------------------------
    # Utility Helpers
    # -------------------------------------------------------------------------

    def _config_bool(self, key: str, default: bool = True) -> bool:
        """Read a boolean config value from deployment config with a default."""
        val = self.get_agent_config(key)
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        if isinstance(val, str):
            return val.lower() in ("true", "1", "yes")
        return bool(val)

    @staticmethod
    def _sanitize_id(raw_id: str) -> str:
        """Sanitize a machine ID for use as a tag key component."""
        sanitized = re.sub(r"[^a-zA-Z0-9]", "_", str(raw_id))
        sanitized = re.sub(r"_+", "_", sanitized).strip("_").lower()
        return sanitized or "unknown"


def _normalize_timestamp(value) -> str:
    """Normalize a timestamp value to UTC ISO 8601 format.

    Handles strings, epoch seconds/millis, and datetime objects.
    Returns an empty string if the value cannot be parsed.
    """
    if not value:
        return ""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, (int, float)):
        # Assume epoch millis if > year 2100 in seconds
        if value > 4_102_444_800:
            value = value / 1000
        try:
            return datetime.fromtimestamp(value, tz=timezone.utc).isoformat()
        except (OSError, OverflowError, ValueError):
            return ""
    if isinstance(value, str):
        return value
    return ""

"""
JCB LiveLink Platform Configuration

Defines user-configurable parameters for the JCB LiveLink telematics integration,
including API connection settings, polling options, and data inclusion toggles.
"""

from pathlib import Path

from pydoover import config


class JcbLivelinkPlatformConfig(config.Schema):
    """Configuration schema for JCB LiveLink Platform processor."""

    def __init__(self):
        # API connection settings
        self.api_base_url = config.String(
            "API Base URL",
            description="Base URL for the JCB LiveLink API",
            default="https://api.jcblivelink.com",
        )
        self.api_token = config.String(
            "API Token",
            description="API authentication token/key obtained from JCB LiveLink",
        )

        # Polling configuration
        self.poll_interval_minutes = config.Integer(
            "Poll Interval (minutes)",
            description="How often to poll the JCB LiveLink API (in minutes). Used as the schedule rate.",
            default=15,
        )

        # Machine selection
        self.machine_ids = config.Array(
            "Machine IDs",
            element=config.String("Machine ID"),
            description="Specific machine IDs to poll. If empty, polls all available machines.",
        )

        # Data inclusion toggles
        self.include_location = config.Boolean(
            "Include Location",
            description="Include GPS location data in tags",
            default=True,
        )
        self.include_fuel = config.Boolean(
            "Include Fuel",
            description="Include fuel consumption data in tags",
            default=True,
        )
        self.include_hours = config.Boolean(
            "Include Hours",
            description="Include operating hours data in tags",
            default=True,
        )
        self.include_alerts = config.Boolean(
            "Include Alerts",
            description="Include alert/notification data in tags",
            default=True,
        )
        self.include_utilisation = config.Boolean(
            "Include Utilisation",
            description="Include utilisation metrics in tags",
            default=True,
        )


def export():
    """Export configuration schema to doover_config.json."""
    JcbLivelinkPlatformConfig().export(
        Path(__file__).parents[2] / "doover_config.json",
        "jcb_livelink_platform",
    )


if __name__ == "__main__":
    export()

# JCB LiveLink Platform

<img src="https://www.logo.wine/a/logo/JCB_(company)/JCB_(company)-Logo.wine.svg" alt="JCB LiveLink Platform Icon" style="max-width: 100px;">

**Pulls machine telematics data from the JCB LiveLink API and publishes it to the Doover platform via the tag system.**

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](https://github.com/getdoover/jcb-livelink-platform)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](https://github.com/getdoover/jcb-livelink-platform/blob/main/LICENSE)

[Getting Started](#getting-started) | [Configuration](#configuration) | [Developer](https://github.com/getdoover/jcb-livelink-platform/blob/main/DEVELOPMENT.md) | [Need Help?](#need-help)

<br/>

## Overview

JCB LiveLink Platform is a Doover processor that integrates with the JCB LiveLink telematics API to retrieve real-time machine data and surface it on the Doover platform. It periodically polls the API to collect information about your JCB fleet, including GPS location, operating hours, fuel consumption, active alerts, and utilisation metrics.

The processor is designed to work with JCB's AEMP-standard telematics endpoints, automatically discovering available fleet and equipment API paths. Each machine's data is normalised and published as individual tags on the Doover platform, making it easy to build dashboards, set up alerts, and monitor your entire JCB fleet from a single interface.

Whether you are tracking a single excavator or managing a fleet of hundreds of machines, this processor handles the data collection, normalisation, and publishing so you can focus on making informed decisions about your equipment.

### Features

- Automatic polling of the JCB LiveLink telematics API on a configurable schedule
- Per-machine GPS location tracking with timestamp and address data
- Operating hours monitoring (total hours and idle hours)
- Fuel consumption tracking (total consumed, remaining percentage, last 24 hours)
- Active alert and fault notification forwarding
- Utilisation and idle percentage metrics
- Configurable data inclusion toggles to control which metrics are collected
- Support for polling all machines or a specific subset by machine ID
- AEMP-standard endpoint discovery with multiple fallback paths
- Manual refresh via message commands (refresh, force-refresh, poll)
- Comprehensive error handling with status and error reporting via tags

<br/>

## Getting Started

### Prerequisites

1. A Doover platform account with access to create and manage processors
2. A JCB LiveLink account with API access enabled
3. An API authentication token obtained from JCB LiveLink
4. The Doover CLI installed and configured

### Installation

Install the processor using the Doover CLI:

```bash
doover app install jcb-livelink-platform
```

Or add it to your Doover agent through the platform interface.

### Quick Start

1. Install the processor on your Doover agent
2. Open the processor configuration in the Doover platform
3. Enter your JCB LiveLink **API Token** (required)
4. Optionally specify **Machine IDs** to poll specific machines, or leave empty to poll all
5. The processor will begin polling automatically on the configured schedule (default: every 15 minutes)
6. View machine data in the Doover tag system

<br/>

## Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| **API Base URL** | Base URL for the JCB LiveLink API | `https://api.jcblivelink.com` |
| **API Token** | API authentication token/key obtained from JCB LiveLink | *Required* |
| **Poll Interval (minutes)** | How often to poll the JCB LiveLink API (in minutes). Used as the schedule rate. | `15` |
| **Machine IDs** | Specific machine IDs to poll. If empty, polls all available machines. | *Required* (empty array polls all) |
| **Include Location** | Include GPS location data in tags | `true` |
| **Include Fuel** | Include fuel consumption data in tags | `true` |
| **Include Hours** | Include operating hours data in tags | `true` |
| **Include Alerts** | Include alert/notification data in tags | `true` |
| **Include Utilisation** | Include utilisation metrics in tags | `true` |

### Example Configuration

```json
{
  "api_base_url": "https://api.jcblivelink.com",
  "api_token": "your-api-token-here",
  "poll_interval_(minutes)": 15,
  "machine_ids": ["MACHINE-001", "MACHINE-002"],
  "include_location": true,
  "include_fuel": true,
  "include_hours": true,
  "include_alerts": true,
  "include_utilisation": true
}
```

<br/>

## Tags

This processor exposes the following tags for each machine and for overall status:

### Global Status Tags

| Tag | Description |
|-----|-------------|
| **last_poll_status** | Status of the most recent API poll (`success`, `error`, or `auth_failed`) |
| **last_poll_timestamp** | ISO 8601 timestamp of the last successful poll |
| **last_error** | Description of the last error encountered (empty string on success) |
| **machine_count** | Number of machines retrieved in the last poll |
| **machines** | Summary object mapping each machine's sanitised ID to its name, model, and last update time |

### Per-Machine Tags

For each machine, tags are published using the pattern `machine_{id}_{category}`, where `{id}` is the sanitised machine identifier. The following per-machine tags are created based on configuration toggles:

| Tag | Description | Toggle |
|-----|-------------|--------|
| **machine_{id}_info** | Machine identity: make, model, serial number, and name | Always included |
| **machine_{id}_location** | GPS coordinates (lat/lon), timestamp, and address | `include_location` |
| **machine_{id}_hours** | Total operating hours and idle hours | `include_hours` |
| **machine_{id}_fuel** | Total fuel consumed, remaining percentage, and last 24h consumption | `include_fuel` |
| **machine_{id}_alerts** | List of active alerts, alarms, or faults | `include_alerts` |
| **machine_{id}_utilisation** | Utilisation percentage and idle percentage | `include_utilisation` |

<br/>

## How It Works

1. **Trigger**: The processor is invoked on a configurable schedule (default every 15 minutes) or manually via a message command (`refresh`, `force-refresh`, or `poll`).
2. **Configuration**: On startup, it reads API connection settings and data inclusion toggles from the Doover deployment configuration, and initialises an HTTP client with Bearer token authentication.
3. **Machine Discovery**: It fetches the list of machines, either using the configured machine IDs or by querying AEMP-style fleet endpoints (`/Fleet`, `/Equipment`, `/machines`) with automatic fallback.
4. **Data Collection**: For each machine, it retrieves detailed telematics data and normalises it into standard categories: info, location, hours, fuel, alerts, and utilisation.
5. **Tag Publishing**: The normalised data is published to the Doover tag system as per-machine tags, along with a global summary including machine count, poll status, and timestamp.
6. **Error Handling**: HTTP errors, authentication failures, and connection issues are caught and reported via `last_poll_status` and `last_error` tags so operators can monitor integration health.

<br/>

## Integrations

This processor works with:

- **JCB LiveLink**: Connects to the JCB LiveLink telematics API to retrieve fleet and machine data using AEMP/ISO 15143-3 standard endpoints.
- **Doover Tag System**: Publishes all collected data as tags on the Doover platform for use in dashboards, alerts, and automation workflows.
- **Doover Scheduler**: Uses the Doover scheduling system for periodic automatic polling at the configured interval.

<br/>

## Need Help?

- Email: support@doover.com
- [Doover Documentation](https://docs.doover.com)
- [App Developer Documentation](https://github.com/getdoover/jcb-livelink-platform/blob/main/DEVELOPMENT.md)

<br/>

## Version History

### v0.1.0 (Current)
- Initial release
- JCB LiveLink API integration with Bearer token authentication
- Automatic fleet discovery via AEMP-style endpoints
- Per-machine telematics data collection (location, hours, fuel, alerts, utilisation)
- Configurable data inclusion toggles
- Scheduled and manual polling support
- Comprehensive error handling and status reporting

<br/>

## License

This app is licensed under the [Apache License 2.0](https://github.com/getdoover/jcb-livelink-platform/blob/main/LICENSE).

# Build Plan

## App Summary
- Name: jcb-livelink-platform
- Type: processor
- Description: A Doover processor that periodically polls the JCB LiveLink API to retrieve machine telematics data (location, fuel, hours, alerts, utilisation) and publishes it to the Doover tag system for display on the platform.

## External Integration
- Service: JCB LiveLink Telematics API
- Documentation: No publicly available REST API documentation found. JCB provides developer toolkit access through their support portal (https://jcblivelink.atlassian.net/servicedesk/customer/portals). The API likely follows AEMP/ISO 15143-3 conventions used by construction equipment OEMs.
- Authentication: API key/token-based (user must obtain credentials from JCB LiveLink). Configuration will support both a base URL and an API token/key to accommodate whatever authentication mechanism JCB provides.

## Research Findings

### JCB LiveLink Data Available
Based on research, JCB LiveLink exposes the following telemetry data for machines:
- **Location**: Real-time GPS coordinates (latitude, longitude), what3words integration
- **Fuel**: Consumption tracking, fuel remaining, CO2 emissions
- **Operating Hours**: Cumulative engine hours, idle hours
- **Utilisation**: Productive usage rates, idle time monitoring
- **Alerts**: Geofence violations, out-of-hours use, maintenance due, seatbelt compliance, boom overload (LLMC)
- **Maintenance**: Service history, diagnostic fault codes, machine health
- **Safety**: Seatbelt monitoring, prestart check results

### AEMP/ISO 15143-3 Standard Fields
The industry standard for construction telematics defines these core fields:
- Equipment identity (OEM, model, serial number)
- Location (timestamped lat/lon)
- Operating hours (cumulative, idle)
- Fuel used (total, last 24h)
- Fuel remaining percentage
- Distance travelled

### API Approach
Since JCB LiveLink does not have publicly documented API endpoints, this processor will be built with a configurable API client that:
1. Uses a configurable base URL and authentication token
2. Implements common AEMP-style endpoint patterns (e.g., `/Fleet`, `/Equipment/{id}`)
3. Includes a generic HTTP client wrapper that can be adapted once the user has API access
4. Falls back to sensible error handling when endpoints are unavailable

## Data Flow
- Inputs: Scheduled trigger (periodic polling of JCB LiveLink API)
- Processing: Fetch machine data from JCB LiveLink API, parse response, map fields to Doover tags
- Outputs: Tags (machine location, fuel, hours, alerts, utilisation, status), connection status pings

### Flow Diagram
```
┌──────────────┐     on_schedule      ┌─────────────────────┐
│   Schedule   │ ──────────────────►  │  jcb-livelink-plat  │
│  (periodic)  │                      │     (processor)      │
└──────────────┘                      └──────────┬──────────┘
                                                 │
                                        HTTP GET │
                                                 ▼
                                      ┌──────────────────┐
                                      │  JCB LiveLink    │
                                      │      API         │
                                      └──────────┬──────┘
                                                 │
                                        JSON/XML │ response
                                                 ▼
                                      ┌──────────────────┐
                                      │  Parse & Map     │
                                      │  to Doover Tags  │
                                      └──────────┬──────┘
                                                 │
                                      set_tag()  │  ping_connection()
                                                 ▼
                                      ┌──────────────────┐
                                      │  Doover Platform │
                                      │  (Tag Display)   │
                                      └──────────────────┘
```

## Configuration Schema
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| api_base_url | String | yes | https://api.jcblivelink.com | Base URL for the JCB LiveLink API |
| api_token | String | yes | (none) | API authentication token/key obtained from JCB |
| poll_interval_minutes | Integer | no | 15 | How often to poll the API (in minutes, used as schedule rate) |
| machine_ids | Array[String] | no | [] | Specific machine IDs to poll. If empty, polls all available machines |
| include_location | Boolean | no | true | Include GPS location data in tags |
| include_fuel | Boolean | no | true | Include fuel consumption data in tags |
| include_hours | Boolean | no | true | Include operating hours data in tags |
| include_alerts | Boolean | no | true | Include alert/notification data in tags |
| include_utilisation | Boolean | no | true | Include utilisation metrics in tags |
| subscription | ManySubscriptionConfig | no | - | Channel subscriptions (for receiving commands/config updates) |
| schedule | ScheduleConfig | no | rate(15 minutes) | Schedule for periodic API polling |

### Subscriptions
- Channel pattern: `cmds` (to receive manual refresh commands or configuration updates from the platform)
- Message types: command messages (e.g., force-refresh, update-config)

### Schedule
- Interval: `rate(15 minutes)` (default, configurable)
- Purpose: Periodically poll JCB LiveLink API for latest machine telematics data

## Event Handlers
| Handler | Trigger | Description |
|---------|---------|-------------|
| setup | Invocation start | Initialize HTTP client, validate API credentials, load config |
| on_schedule | rate(15 minutes) | Poll JCB LiveLink API, parse response, update Doover tags for each machine |
| on_message_create | Channel message (cmds) | Handle manual refresh commands or configuration updates |
| close | Invocation end | Clean up HTTP client resources |

### Handler Details

#### setup()
- Initialize `aiohttp` or `httpx` async HTTP client session
- Read API credentials from config
- Validate that api_base_url and api_token are configured
- Set up request headers (Authorization, Content-Type, User-Agent)

#### on_schedule()
1. Fetch list of machines from API (or use configured machine_ids)
2. For each machine, fetch telematics data:
   - Location (lat, lon, timestamp)
   - Operating hours (total, idle)
   - Fuel data (consumed, remaining %)
   - Alerts (active alerts, counts)
   - Utilisation (percentage, idle time)
3. Map API response to Doover tags per machine
4. Call `set_tag()` for each data point
5. Call `ping_connection()` to update connection status
6. Store last successful poll timestamp in tags
7. Handle API errors gracefully (store error state in tags)

#### on_message_create()
- Listen on `cmds` channel for manual refresh commands
- On receiving a refresh command, trigger an immediate API poll
- Handle any configuration update messages

## Tags (Output)
| Tag Name | Type | Description |
|----------|------|-------------|
| machines | object | Dictionary of all machine data keyed by machine ID |
| machine_{id}_location | object | `{lat, lon, timestamp, address}` for a specific machine |
| machine_{id}_hours | object | `{total_hours, idle_hours, last_updated}` for a machine |
| machine_{id}_fuel | object | `{total_consumed, remaining_pct, last_24h, last_updated}` for a machine |
| machine_{id}_alerts | array | List of active alerts for a machine |
| machine_{id}_utilisation | object | `{utilisation_pct, idle_pct, last_updated}` for a machine |
| machine_{id}_info | object | `{make, model, serial, name}` machine identity info |
| last_poll_timestamp | string | ISO timestamp of last successful API poll |
| last_poll_status | string | Status of last poll: "success", "error", "auth_failed" |
| last_error | string | Description of last error encountered (if any) |
| machine_count | integer | Number of machines retrieved from API |

## UI Elements
N/A - has_ui is false. Data is displayed via the Doover tag system directly.

## Documentation Chunks

### Required Chunks
- `config-schema.md` - Configuration types and patterns (String, Boolean, Integer, Array, Schema export)
- `cloud-handler.md` - Handler and event patterns (on_schedule, on_message_create, setup, close)
- `cloud-project.md` - Project setup and build script (build.sh, package.zip, pyproject.toml)
- `processor-features.md` - ManySubscriptionConfig, ScheduleConfig, connection status, ping_connection

### Recommended Chunks
- `tags-channels.md` - Tag get/set patterns, channel publishing, cloud app async tag operations

### Discovery Keywords
subscription, schedule, rate, set_tag, get_tag, ping_connection, connection, aiohttp, httpx, async

## Implementation Notes
- **HTTP Client**: Use `aiohttp` (already common in the pydoover ecosystem) for async HTTP requests to the JCB LiveLink API. Add `aiohttp` as a dependency in `pyproject.toml`.
- **Authentication**: Design a flexible auth module that supports bearer token, API key header, and basic auth patterns. The user will configure which method is needed based on their JCB LiveLink API access.
- **Error Handling**: Implement robust error handling for API failures (timeouts, auth errors, rate limiting). Store error state in tags so the platform can display connectivity issues.
- **Idempotent Polling**: Each scheduled invocation independently polls and overwrites tag data. No cross-invocation state dependencies beyond tags.
- **Rate Limiting**: Respect JCB API rate limits. Default 15-minute polling interval is conservative. Implement exponential backoff on failures.
- **Cold Start Optimization**: Keep the handler lightweight. Initialize HTTP client in setup(), close in close(). No heavy imports at module level.
- **Data Normalization**: Normalize all timestamps to UTC ISO 8601 format. Normalize units to metric (SI).
- **Machine ID Handling**: Support both "all machines" mode (empty machine_ids config) and "specific machines" mode (configured list). Machine IDs in tag names should be sanitized for use as tag keys.
- **Connection Status**: Use `ping_connection()` after each successful poll to update the device connection status on the Doover platform, showing when data was last successfully retrieved.
- **Existing Template Code**: The current app was scaffolded from a Docker app template. The build phase must convert it to a proper cloud/processor structure:
  - Replace `pydoover.docker` imports with `pydoover.cloud.processor` imports
  - Replace `main()` entry point with `handler()` entry point
  - Replace `main_loop()` with event handlers (`on_schedule`, `on_message_create`)
  - Remove `app_state.py` (state machine not needed; use tags for state)
  - Add `build.sh` for deployment package creation
  - Update `pyproject.toml` to remove docker-specific config and add aiohttp dependency
  - Add `ManySubscriptionConfig` and `ScheduleConfig` to config schema

# Weather Provider Integration Setup & Operations Runbook

## Purpose and scope

This runbook covers the incident weather integration used when the driver incident protocol requests weather evidence for an incident. It documents:

- National Weather Service (NWS) textual/time-series weather capture.
- Mapbox static satellite basemap capture.
- The Weather Company (TWC) radar overlay capture.
- Runtime configuration, secret requirements, degraded behavior, QA acceptance mapping, and operational signals.

**Scope note:** the initial accident PDF update is limited to the `crash_brief` PDF template/rendering path only. Do not assume other export PDFs, insurance forms, or downstream package documents include the weather narrative/map changes until a separate acceptance criterion and template update explicitly says so.

## Provider integration setup

### NWS weather time-series provider

| Item | Requirement |
| --- | --- |
| Purpose | Fetch NWS time-series XML for the incident location and request window, then normalize it into weather context persisted on weather lifecycle events. |
| Endpoint | The NWS client currently calls the hard-coded `https://forecast.weather.gov/MapClick.php` endpoint for the `time-series` product. `NWS_BASE_URL` is validated by configuration checks but is not used as the request target. |
| Credentials | None. NWS requests do not require an API token. |
| Network allow-list | Allow outbound HTTPS to `forecast.weather.gov`. Configuring or allow-listing only `NWS_BASE_URL` is not sufficient unless the client is changed to use that value. |
| Retry/timeout knobs | `NWS_REQUEST_TIMEOUT_SECONDS` and `NWS_REQUEST_MAX_RETRIES` control the current NWS request loop. The loop retries immediately; weather retry backoff settings are validated but are not currently read by the NWS client. |
| Expected artifact/event | `weather_snapshot_requested`, then either `weather_snapshot_captured` or `weather_snapshot_failed`. |

Setup steps:

1. Confirm outbound HTTPS from backend workers to `forecast.weather.gov`.
2. Keep `NWS_BASE_URL=https://api.weather.gov` for readiness/config validation; do not rely on it as an NWS proxy switch. If staging/prod must route NWS through a proxy, update the NWS client first and cover that behavior with tests.
3. Set `NWS_REQUEST_TIMEOUT_SECONDS` and `NWS_REQUEST_MAX_RETRIES` to match the current incident-initiation SLA. Avoid long timeouts because weather capture must not block the driver protocol.
4. Run the targeted NWS parser/client tests before promotion.

### Mapbox static basemap provider

| Item | Requirement |
| --- | --- |
| Purpose | Render a `1280x720@2x` static satellite basemap centered on the resolved incident location. |
| Endpoint | `https://api.mapbox.com/styles/v1/mapbox/satellite-v9/static/...` |
| Credentials | `MAPBOX_TOKEN` is required outside local tests for weather map snapshot capture. |
| Network allow-list | Allow outbound HTTPS to `api.mapbox.com`. |
| Expected artifact/event | A `weather_map_snapshot` artifact when the map image is persisted, with `weather_map_snapshot_captured` event payload fields. |

Setup steps:

1. Create a Mapbox token scoped for static images.
2. Store it as `MAPBOX_TOKEN` in the active secret backend.
3. Verify the token can request `mapbox/satellite-v9` static images at `1280x720@2x`.
4. Confirm `S3_ARTIFACTS_BUCKET` and `AWS_REGION` are configured because the rendered map is persisted as an incident artifact.

### TWC radar overlay provider

| Item | Requirement |
| --- | --- |
| Purpose | Fetch the latest TWC radar timeslice metadata and overlay PNG, then alpha-composite it over the Mapbox basemap. |
| Endpoint | `https://api.weather.com/v3/TileServer/tile` with `product=radar`, `ts=latest`, incident `lat`/`lon`, and `apiKey`. The returned metadata points to the overlay image URL. |
| Credentials | `TWC_API_KEY` is required for radar overlays. |
| Network allow-list | Allow outbound HTTPS to `api.weather.com` and the overlay image host returned by TWC metadata. |
| Degraded behavior | TWC overlay failures currently produce a base-map-only weather map snapshot with `capture_status=degraded` because the incident workflow calls the capture service with base-only fallback enabled. There is no environment variable that disables this fallback. |

Setup steps:

1. Provision a TWC API key with radar tile/timeslice access.
2. Store it as `TWC_API_KEY` in the active secret backend.
3. Test both metadata and overlay URL access from the backend worker network.
4. Plan operational expectations around the current base-map-only fallback: overlays can be unavailable while the artifact is still captured as degraded. If an environment must fail hard when overlays are unavailable, add a real runtime/configuration path before documenting that policy.

## Config and secret requirements

### Required runtime configuration

| Variable | Secret? | Required for | Notes |
| --- | --- | --- | --- |
| `NWS_BASE_URL` | No | NWS readiness/config validation only | Must be an `http(s)` URL. Default is `https://api.weather.gov`; the current NWS client does not use this value for requests. |
| `NWS_REQUEST_TIMEOUT_SECONDS` | No | NWS capture | Must be greater than `0`. |
| `NWS_REQUEST_MAX_RETRIES` | No | NWS capture | Must be `>= 0`. |
| `MAPBOX_TOKEN` | Yes | Weather map basemap capture | Missing token fails map rendering with `Mapbox configuration missing`. |
| `TWC_API_KEY` | Yes | Radar overlay capture | Missing key degrades to base-map-only under the current incident workflow because base-only fallback is enabled. |
| `WEATHER_DEFAULT_UNITS` | No | Config validation only | Allowed values: `e`, `m`, `h`; the current NWS query builder still uses its hard-coded default unit (`e`) unless code passes a different unit. |
| `WEATHER_DEFAULT_MAP_DIMENSIONS` | No | Map rendering validation | Must remain `1280x720@2x` for the supported PDF/layout baseline. |
| `WEATHER_RETRY_BASE_BACKOFF_SECONDS` | No | Config validation only | Must be greater than `0`; not currently read by the NWS retry loop. |
| `WEATHER_RETRY_BACKOFF_MULTIPLIER` | No | Config validation only | Must be `>= 1`; not currently read by the NWS retry loop. |
| `WEATHER_RETRY_MAX_BACKOFF_SECONDS` | No | Config validation only | Must be greater than or equal to the base backoff; not currently read by the NWS retry loop. |
| `S3_ARTIFACTS_BUCKET` | Yes/controlled config | Weather map artifact persistence | Required for persisted map snapshots. |
| `AWS_REGION` | No | Artifact persistence | Used by S3-backed artifact storage. |
| `SECRET_PROVIDER` | No | Secret loading | `env` or `aws_secrets_manager`. |
| `AWS_SECRETS_MANAGER_SECRET_ID` | Yes/controlled config | Secret loading | Required when `SECRET_PROVIDER=aws_secrets_manager`. |

### Secret handling expectations

- Keep `MAPBOX_TOKEN` and `TWC_API_KEY` out of logs, screenshots, support tickets, and QA evidence attachments.
- Use `SECRET_PROVIDER=aws_secrets_manager` for staging/prod when available; otherwise inject secrets through the platform secret manager into environment variables.
- Rotate Mapbox/TWC credentials after vendor-side compromise, accidental disclosure, or team access changes. Validate both successful map capture and degraded overlay behavior after rotation.
- Do not make TWC mandatory for all accident initiation flows unless Product and Support accept the increased failure risk; base-map-only degraded capture is the current resilience posture.

## Fallback resolution logic

Weather capture first resolves a location. Both textual weather snapshots and map snapshots use the same location resolution order:

1. **Driver device location** from the latest `incident_protocol_initiated` event payload with `device_location.lat/lon` or `device_location.latitude/longitude`.
2. **Current ELD/telematics GPS window** matching `samsara_vehicle_id` or `adc_vehicle_id` in the request window.
3. **Last-known ELD/telematics vehicle state** matching `samsara_vehicle_id` or `adc_vehicle_id`.
4. **Unavailable** with `fallback_reason=no_location_available` when no usable coordinates exist, or `incident_not_found` if the incident row is missing.

Resolution results are copied into event payloads as:

```json
{
  "location": {
    "lat": 40.123,
    "lon": -105.456,
    "source": "device_location | eld_current | eld_last_known | unavailable",
    "fallback_reason": null
  }
}
```

### Degraded and failed behavior

| Condition | Expected backend status | User-facing/degraded UX guidance |
| --- | --- | --- |
| NWS normalized response is partial | `weather_snapshot_captured` with `capture_status=degraded`, `degraded=true` | Show weather summary with a warning such as: “Weather data is partial; verify critical values before relying on this packet.” |
| Missing location/request window for NWS | `weather_snapshot_failed`, `reason=insufficient_request_context` | Show “Weather unavailable because incident time/location was incomplete.” Do not block incident initiation. |
| Mapbox token missing or Mapbox fetch fails | `weather_map_snapshot_failed`, `reason=RuntimeError` or HTTP/client error class | Show “Weather map unavailable.” Keep crash workflow usable and expose retry/admin escalation. |
| TWC key missing | Base map captured with `capture_status=degraded`, `overlay_applied=false`, `overlay_unavailable_reason=twc_api_key_missing` under the current base-only fallback | Show “Radar overlay unavailable; map shown without radar.” |
| TWC metadata empty/invalid or overlay fetch fails | Base map captured with `capture_status=degraded`, `overlay_applied=false`, reason such as `twc_timeslice_empty`, `twc_timeslice_invalid_json`, `twc_overlay_http_403` | Show “Radar overlay unavailable; base map captured.” Include provider reason in admin-only diagnostics, not driver-facing copy. |
| Artifact storage write fails | `weather_map_snapshot_failed`, reason from storage exception | Show “Weather map could not be saved.” On-call should inspect S3/object storage health. |

Driver-facing and claimant-facing copy should be plain-language and avoid vendor names unless necessary. Admin/on-call diagnostics may show provider names, status codes, and reason codes.

## Stale or missing overlay troubleshooting

Use this sequence when QA, Support, or on-call reports a stale/missing radar overlay or absent weather map.

1. **Confirm the lifecycle event state.** Query incident events for `weather_map_snapshot_requested`, `weather_map_snapshot_captured`, and `weather_map_snapshot_failed`.
2. **Inspect event payload fields.** Check `capture_status`, `degraded`, `overlay_applied`, `overlay_unavailable_reason`, `twc_radar_timestamp`, `artifact_id`, and `location.source`.
3. **Classify the symptom.**
   - No `weather_map_snapshot_requested`: capture task was not enqueued or incident initiation did not reach weather request logic.
   - `weather_map_snapshot_failed` with `location_unavailable`: GPS/device/telematics fallback failed; inspect location resolution inputs.
   - `capture_status=degraded` and `overlay_applied=false`: Mapbox base image succeeded, but TWC overlay failed or was unavailable.
   - `capture_status=ok` but radar visually stale: compare `twc_radar_timestamp` with the incident/request time and provider metadata.
   - `artifact_id` present but image missing: inspect artifact storage and S3 object metadata.
4. **Validate secrets and provider access.** Check that `MAPBOX_TOKEN` and `TWC_API_KEY` are populated in the worker runtime and have not expired, been revoked, or lost required scopes.
5. **Check provider response class.** Use the recorded `overlay_unavailable_reason`:
   - `twc_api_key_missing`: fix secret injection.
   - `twc_timeslice_http_401`/`403`: rotate or re-scope TWC key.
   - `twc_timeslice_http_429`: rate limiting; reduce retry pressure and contact vendor if sustained.
   - `twc_timeslice_empty`: provider has no radar series for the coordinates/time; verify the coordinates and retry later.
   - `twc_overlay_http_*` or `twc_overlay_transport_error`: overlay image host/network issue.
6. **Check artifact persistence.** Confirm `S3_ARTIFACTS_BUCKET`, `AWS_REGION`, object write permissions, checksum metadata, and bucket availability.
7. **Retry safely.** A failed/captured map snapshot is treated as terminal for duplicate prevention. Use an approved admin repair/re-drive procedure rather than repeatedly initiating the driver protocol.
8. **Escalate with evidence.** Include incident ID, org ID, request window, location source, provider reason code, artifact ID/key if available, and dashboard snapshots. Do not include raw API tokens.

## Operational signals for on-call

### Structured logs

Watch for these log messages:

| Logger message | Key fields | Interpretation |
| --- | --- | --- |
| `weather_snapshot_capture` | `incident_id`, `provider=nws`, `status`, `latency` | NWS textual capture result. `status` is typically `ok`, `degraded`, or `failed`. |
| `weather_map_snapshot_capture` | `incident_id`, `provider=mapbox+twc`, `status`, `latency` | Weather map result. `status=degraded` usually means base map saved without radar overlay. |

Recommended log search fields to add to dashboards: `incident_id`, `org_id` when available from request context, `provider`, `status`, `latency`, `event_type`, `capture_status`, `reason`, `overlay_unavailable_reason`, `location.source`, `location.fallback_reason`, `artifact_id`.

### Metrics

The weather providers currently use the shared integration metric names below without provider labels. Treat these counters as aggregate integration signals that may include non-weather providers such as Twilio, FMCSA, and Samsara. Use structured logs and weather lifecycle events, not provider-labelled metric selectors, when a dashboard or alert must isolate NWS/Mapbox/TWC behavior.

| Metric name | Use |
| --- | --- |
| `integration.provider.requests` | Count of provider capture attempts. |
| `integration.provider.success` | Successful provider capture. Map snapshots with base-only degraded output still increment success after artifact capture. |
| `integration.provider.failure` | Failed capture attempts, including missing location, provider hard failure, or artifact persistence failure. |
| `integration.provider.timeout` | Provider timeout counter when emitted by shared integration instrumentation. |
| `integration.provider.rate_limit` | Provider rate-limit counter when emitted by shared integration instrumentation. |
| `integration.provider.auth_failure` | Provider auth/credential failure counter when emitted by shared integration instrumentation. |
| `integration.provider.latency.duration_ms` | Timed provider request/capture latency emitted by the `timed()` helper. The base metric name is passed in code, but the recorded timing series appends `.duration_ms`. |

### Alerting hints

Start with conservative alerts and tune after baseline traffic is available:

- **Weather hard-failure rate:** page during business-critical windows when weather lifecycle events or structured logs show failed NWS/map snapshot captures above the release threshold for 15 minutes, or when any single enterprise tenant has repeated accident packets without weather evidence. Do not rely on `provider` labels on `integration.provider.failure`; current shared metrics are unlabelled aggregate counters.
- **Mapbox auth/config regression:** page if `weather_map_snapshot_failed` spikes with `reason=RuntimeError` (missing token/config) or `reason=HTTPStatusError` after deploy/secret rotation. The failed event payload does not currently retain Mapbox HTTP status codes, so separate 401/403-specific alerting requires additional instrumentation or vendor/request logs.
- **TWC overlay degradation:** warn (ticket, not page) if `overlay_applied=false` exceeds 25% for 30 minutes while Mapbox capture remains successful; page only if customer commitments require radar overlays.
- **Stale radar:** warn if `twc_radar_timestamp` is older than the incident/request window by the Product-approved threshold, or if timestamps stop advancing globally.
- **Location fallback exhaustion:** page if `location.source=unavailable` rises above 10% for accident initiations, because downstream evidence capture quality is at risk.
- **Artifact persistence:** page if `weather_map_snapshot_failed` reasons correlate with S3/object-storage errors or if captured events have missing artifacts.

## QA checklist mapped to acceptance criteria

| Acceptance criterion | QA entry | Automated/regression coverage | Manual evidence to retain |
| --- | --- | --- | --- |
| **WX-AC-1 NWS capture is non-blocking and normalized.** | Initiate an incident with valid location/time and verify `weather_snapshot_requested` then `weather_snapshot_captured`; repeat with partial NWS XML fixture and verify degraded normalization. | `backend/tests/services/test_nws_client.py`, `backend/tests/services/test_nws_parser.py`, `backend/tests/services/test_weather_snapshot_service.py` | Event payload screenshot/log extract with `capture_status`, normalized weather fields, and request window. |
| **WX-AC-2 Location fallback order is deterministic.** | Seed incidents with device location, current ELD GPS, last-known ELD state, and no location; verify source order and unavailable reasons. | `backend/tests/test_incident_location_resolver.py` | Table of incident IDs mapped to `location.source` and `fallback_reason`. |
| **WX-AC-3 Weather map captures Mapbox base image and TWC overlay when both providers are healthy.** | Run capture with valid `MAPBOX_TOKEN` and `TWC_API_KEY`; verify `weather_map_snapshot_captured`, `overlay_applied=true`, `twc_radar_timestamp`, and persisted artifact. | `backend/tests/services/test_weather_map_snapshot_service.py` | Artifact preview, event payload, S3/object metadata, and provider timestamps. |
| **WX-AC-4 TWC overlay failure degrades without blocking the incident workflow.** | Remove/deny TWC key or simulate TWC metadata/overlay error in the current incident workflow; verify base map artifact is captured with `capture_status=degraded`. | `backend/tests/services/test_weather_map_snapshot_service.py` | Event payload with `overlay_applied=false` and `overlay_unavailable_reason`; screenshot/preview of base map only. |
| **WX-AC-5 Missing location or provider/storage hard failure produces actionable diagnostics.** | Simulate no location, Mapbox config failure, and artifact storage failure; verify failed events include reason/fallback fields and user workflow remains usable. | `backend/tests/services/test_weather_snapshot_service.py`, `backend/tests/services/test_weather_map_snapshot_service.py`, `backend/tests/test_incident_workflow_service.py` | Failed event payloads and UX copy showing non-blocking degraded messaging. |
| **WX-AC-6 Accident PDF scope is limited to `crash_brief`.** | Generate/update accident PDF evidence and verify weather changes appear only in `crash_brief`; confirm no unrelated PDF templates changed. | `backend/tests/test_crash_packet_builder.py`, `backend/tests/test_pdf_render_templates.py`, `backend/tests/test_export_pdf_service.py` as applicable to the implementation PR | Rendered `crash_brief` PDF and diff/review note confirming other PDFs are unchanged unless separately approved. |
| **WX-AC-7 On-call can diagnose without code spelunking.** | Trigger ok/degraded/failed weather captures in staging and confirm structured logs/events, aggregate metrics, dashboards, and alert runbooks expose provider, reason, latency, incident ID, artifact ID, and fallback source where each signal actually records those fields. | CI lint/type/tests plus dashboard/runbook review | Dashboard screenshot, sample log query, alert rule link, and this runbook link in the release ticket. |

## Promotion checklist

Before promoting a release that changes weather capture or accident PDF rendering:

- [ ] Backend lint, type checks, and tests pass.
- [ ] `MAPBOX_TOKEN` and `TWC_API_KEY` are present in staging/prod secret inventory or the release explicitly accepts degraded map behavior.
- [ ] NWS/Mapbox/TWC outbound network paths are allowed from worker runtime.
- [ ] Weather map artifact writes succeed in the target `S3_ARTIFACTS_BUCKET`.
- [ ] Staging has at least one successful full overlay capture and one exercised base-only degraded capture.
- [ ] `crash_brief` PDF output has been reviewed, and scope has not expanded to other PDFs without explicit acceptance criteria.
- [ ] On-call dashboards include the logs/metrics fields listed above.

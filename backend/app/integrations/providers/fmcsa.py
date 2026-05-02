"""FMCSA MCMIS roadside-inspection provider.

Pulls inspection records for a single carrier (USDOT) from the public
Socrata dataset ``fx4q-ay7w`` over the SoQL v3 endpoint.

Responses are returned as raw dicts; downstream normalization happens
in :mod:`app.services.driver_violation_history_capture_service`.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import settings
from app.core.metrics import MetricNames, increment, timed

logger = logging.getLogger(__name__)


# Socrata endpoint for the FMCSA roadside-inspections dataset.
DATASET_ID = "fx4q-ay7w"
DEFAULT_PAGE_SIZE = 1000


class FmcsaProvider:
    """Provider for FMCSA MCMIS roadside inspections via Socrata."""

    def __init__(
        self,
        app_token: str | None = None,
        base_url: str | None = None,
        page_size: int = DEFAULT_PAGE_SIZE,
    ):
        self.app_token = (
            app_token if app_token is not None else settings.SOCRATA_APP_TOKEN
        )
        self.base_url = (
            base_url
            if base_url is not None
            else getattr(settings, "FMCSA_BASE_URL", "https://data.transportation.gov")
        ).rstrip("/")
        self.page_size = page_size

    @property
    def _endpoint(self) -> str:
        return f"{self.base_url}/api/v3/views/{DATASET_ID}/query.json"

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        token = (self.app_token or "").strip()
        if token:
            headers["X-App-Token"] = token
        return headers

    @staticmethod
    def _build_query(
        *, usdot_number: str, since: str, until: str, limit: int, offset: int
    ) -> dict[str, Any]:
        # SoQL filtered fetch. ``dot_number`` and ``insp_date`` are the
        # canonical column names on the public dataset.
        soql = (
            f"SELECT * "
            f"WHERE dot_number = '{usdot_number}' "
            f"AND insp_date BETWEEN '{since}' AND '{until}' "
            f"ORDER BY insp_date DESC "
            f"LIMIT {int(limit)} OFFSET {int(offset)}"
        )
        return {"query": soql}

    def fetch_inspections(
        self,
        *,
        usdot_number: str,
        since: str,
        until: str,
    ) -> list[dict[str, Any]]:
        """Return all inspection rows for a carrier in ``[since, until]``."""
        results: list[dict[str, Any]] = []
        offset = 0

        while True:
            payload = self._build_query(
                usdot_number=usdot_number,
                since=since,
                until=until,
                limit=self.page_size,
                offset=offset,
            )
            increment(MetricNames.INTEGRATION_PROVIDER_REQUESTS)
            with timed(MetricNames.INTEGRATION_PROVIDER_LATENCY):
                try:
                    with httpx.Client(timeout=30.0) as client:
                        resp = client.post(
                            self._endpoint,
                            headers=self._headers(),
                            json=payload,
                        )
                        resp.raise_for_status()
                        body = resp.json()
                except httpx.TimeoutException:
                    increment(MetricNames.INTEGRATION_PROVIDER_TIMEOUT)
                    increment(MetricNames.INTEGRATION_PROVIDER_FAILURE)
                    raise
                except httpx.HTTPStatusError as exc:
                    status_code = exc.response.status_code
                    if status_code in {401, 403}:
                        increment(MetricNames.INTEGRATION_PROVIDER_AUTH_FAILURE)
                    elif status_code == 429:
                        increment(MetricNames.INTEGRATION_PROVIDER_RATE_LIMIT)
                    increment(MetricNames.INTEGRATION_PROVIDER_FAILURE)
                    raise
                except httpx.HTTPError:
                    increment(MetricNames.INTEGRATION_PROVIDER_FAILURE)
                    raise

            increment(MetricNames.INTEGRATION_PROVIDER_SUCCESS)
            page = body if isinstance(body, list) else body.get("data", [])
            if not page:
                break
            results.extend(page)
            if len(page) < self.page_size:
                break
            offset += self.page_size

        return results

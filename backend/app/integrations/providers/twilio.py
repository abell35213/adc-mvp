"""Twilio messaging/verify provider adapter."""

from __future__ import annotations

import logging
from typing import Any
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.sax.saxutils import escape

import httpx

from app.core.config import settings
from app.core.metrics import MetricNames, increment, timed

logger = logging.getLogger(__name__)

TWILIO_API_BASE = "https://api.twilio.com/2010-04-01/Accounts"


class TwilioMessagingProvider:
    def _require_setting(self, name: str, value: str) -> str:
        if not value:
            raise ValueError(f"{name} is not configured")
        return value

    def _twilio_auth(self) -> tuple[str, str]:
        account_sid = self._require_setting("TWILIO_ACCOUNT_SID", settings.TWILIO_ACCOUNT_SID)
        auth_token = self._require_setting("TWILIO_AUTH_TOKEN", settings.TWILIO_AUTH_TOKEN)
        return account_sid, auth_token

    def _twilio_url(self, path: str) -> str:
        account_sid = self._require_setting("TWILIO_ACCOUNT_SID", settings.TWILIO_ACCOUNT_SID)
        return f"{TWILIO_API_BASE}/{account_sid}/{path}"

    def _post_twilio(self, path: str, data: dict[str, str]) -> dict[str, Any]:
        increment(MetricNames.INTEGRATION_PROVIDER_REQUESTS)
        with timed(MetricNames.INTEGRATION_PROVIDER_LATENCY):
            url = self._twilio_url(path)
            account_sid, auth_token = self._twilio_auth()
            try:
                with httpx.Client() as client:
                    response = client.post(
                        url,
                        data=data,
                        auth=(account_sid, auth_token),
                        timeout=10.0,
                    )
                response.raise_for_status()
                payload = response.json()
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

        if not isinstance(payload, dict):
            raise ValueError(
                "Unexpected Twilio response payload: expected dict, got "
                f"{type(payload).__name__}"
            )
        return payload

    def send_sms(self, to: str, message: str) -> str:
        increment("twilio.send_sms.attempts")
        from_number = self._require_setting("TWILIO_SMS_FROM", settings.TWILIO_SMS_FROM)
        try:
            payload = self._post_twilio(
                "Messages.json",
                {
                    "To": to,
                    "From": from_number,
                    "Body": message,
                },
            )
        except Exception:
            increment(MetricNames.TWILIO_SEND_SMS_FAILURES)
            raise

        sid = payload.get("sid")
        if not sid:
            increment(MetricNames.TWILIO_SEND_SMS_FAILURES)
            raise ValueError(f"Twilio SMS response missing SID. Response: {payload}")
        return sid

    def lookup_delivery_status(self, message_id: str) -> str | None:
        account_sid, auth_token = self._twilio_auth()
        with httpx.Client() as client:
            response = client.get(
                self._twilio_url(f"Messages/{message_id}.json"),
                auth=(account_sid, auth_token),
                timeout=10.0,
            )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            status = payload.get("status")
            if isinstance(status, str):
                return status
        return None

    def place_call(self, to: str, twiml_content: str) -> str:
        increment("twilio.place_call.attempts")
        from_number = self._require_setting("TWILIO_VOICE_FROM", settings.TWILIO_VOICE_FROM)
        data = {"To": to, "From": from_number}
        stripped_value = twiml_content.strip()
        if stripped_value.startswith(("http://", "https://")):
            data["Url"] = stripped_value
        else:
            data["Twiml"] = stripped_value

        try:
            payload = self._post_twilio("Calls.json", data)
        except Exception:
            increment(MetricNames.TWILIO_PLACE_CALL_FAILURES)
            raise

        sid = payload.get("sid")
        if not sid:
            increment(MetricNames.TWILIO_PLACE_CALL_FAILURES)
            raise ValueError(f"Twilio call response missing SID. Response: {payload}")
        return sid

    def build_voice_twiml(self, message: str) -> str:
        response = Element("Response")
        say = SubElement(response, "Say")
        say.text = escape(message)
        return f'<?xml version="1.0" encoding="UTF-8"?>{tostring(response, encoding="unicode")}'

    def _verify_url(self, resource: str) -> str:
        account_sid = settings.TWILIO_ACCOUNT_SID.strip()
        auth_token = settings.TWILIO_AUTH_TOKEN.strip()
        service_sid = settings.TWILIO_VERIFY_SERVICE_SID.strip()
        if not (account_sid and auth_token and service_sid):
            raise RuntimeError("Twilio Verify is not configured")
        return f"https://verify.twilio.com/v2/Services/{service_sid}/{resource}"

    def start_verification(self, phone_e164: str) -> str:
        increment(MetricNames.OTP_DELIVERY_ATTEMPTS)
        try:
            response = httpx.post(
                self._verify_url("Verifications"),
                auth=self._twilio_auth(),
                data={"To": phone_e164, "Channel": "sms"},
                timeout=10.0,
            )
            response.raise_for_status()
        except httpx.TimeoutException:
            increment(MetricNames.OTP_DELIVERY_TIMEOUT)
            increment(MetricNames.OTP_DELIVERY_FAILURE)
            raise
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            if status_code in {401, 403}:
                increment(MetricNames.OTP_DELIVERY_AUTH_FAILURE)
            elif status_code == 429:
                increment(MetricNames.OTP_DELIVERY_RATE_LIMIT)
            increment(MetricNames.OTP_DELIVERY_FAILURE)
            raise
        except httpx.HTTPError:
            increment(MetricNames.OTP_DELIVERY_FAILURE)
            raise

        payload = response.json()
        sid = payload.get("sid")
        if not isinstance(sid, str) or not sid:
            increment(MetricNames.OTP_DELIVERY_FAILURE)
            raise RuntimeError(f"Twilio Verify response missing sid: {payload!r}")
        increment(MetricNames.OTP_DELIVERY_SUCCESS)
        logger.info("Twilio verification started sid=%s", sid)
        return sid

    def check_verification(self, phone_e164: str, otp: str) -> bool:
        response = httpx.post(
            self._verify_url("VerificationCheck"),
            auth=self._twilio_auth(),
            data={"To": phone_e164, "Code": otp},
            timeout=10.0,
        )
        response.raise_for_status()
        status = response.json().get("status")
        return status == "approved"

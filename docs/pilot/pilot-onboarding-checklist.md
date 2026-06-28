# Pilot Onboarding Checklist

## Org setup

- Confirm legal entity name, billing owner, and support contact.
- Create the org and assign the primary admin user.
- Confirm `FRONTEND_ORIGIN`, API URL, and pilot branding requirements.

## Users

- Create safety/admin users.
- Confirm MFA expectations for admins.
- Verify least-privilege role assignments.

## Drivers

- Import or create pilot drivers.
- Verify each driver has a valid phone number for OTP.
- Confirm at least one staged driver can complete a sample login.

## Vehicles

- Create or import pilot vehicles.
- Validate driver-to-vehicle assignments.
- Print and stage QR assets for each vehicle.

## QR deployment

- Place QR materials in the agreed cab / visor location.
- Verify scan resolves the intended tenant and vehicle.
- Confirm damaged QR replacement process with the customer.

## Notification recipients

- Configure safety/legal escalation recipients.
- Verify phone/email routing for crash notifications.
- Confirm after-hours escalation owner.

## Twilio verification

- Confirm Twilio Verify credentials are loaded from Secrets Manager.
- Validate OTP request and OTP verify in staging.
- Confirm fallback/help procedure for OTP failures.

## Telematics / provider configuration

- Load Samsara or other provider credentials.
- Validate at least one sample vehicle/driver mapping.
- Confirm provider outage fallback expectations.

## Sample incident

- Run one staged incident from QR scan through evidence capture.
- Verify safety manager visibility in the web UI.
- Confirm required evidence prompts appear.

## Export validation

- Generate a legal-defense packet for the sample incident.
- Download the export.
- Confirm key sections, attachments, and audit trail are present.

## Support escalation

- Share the operator triage runbook.
- Confirm customer support contacts and severity definitions.
- Schedule the first-week pilot check-in.

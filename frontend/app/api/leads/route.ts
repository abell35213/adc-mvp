import { NextResponse } from "next/server";

interface LeadPayload {
  name: string;
  email: string;
  message: string;
}

function isLeadPayload(payload: unknown): payload is LeadPayload {
  if (!payload || typeof payload !== "object") {
    return false;
  }

  const parsed = payload as Partial<LeadPayload>;

  return (
    typeof parsed.name === "string" &&
    parsed.name.trim().length > 0 &&
    typeof parsed.email === "string" &&
    parsed.email.trim().length > 0 &&
    typeof parsed.message === "string" &&
    parsed.message.trim().length > 0
  );
}

export async function POST(request: Request) {
  const webhookUrl = process.env.MARKETING_LEADS_WEBHOOK_URL;

  if (!webhookUrl) {
    return NextResponse.json(
      { detail: "Lead intake unavailable." },
      { status: 503 }
    );
  }

  const payload = await request.json().catch(() => null);

  if (!isLeadPayload(payload)) {
    return NextResponse.json(
      { detail: "Invalid lead payload." },
      { status: 400 }
    );
  }

  const webhookResponse = await fetch(webhookUrl, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      ...payload,
      source: "company-contact",
      submitted_at_utc: new Date().toISOString(),
    }),
    cache: "no-store",
  });

  if (!webhookResponse.ok) {
    return NextResponse.json(
      { detail: "Lead delivery failed." },
      { status: 502 }
    );
  }

  return NextResponse.json({ ok: true }, { status: 202 });
}

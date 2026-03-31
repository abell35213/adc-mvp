"use client";

import { FormEvent, useState } from "react";
import { trackCtaClick } from "@/lib/tracking";

export default function LeadForm() {
  const [submitted, setSubmitted] = useState(false);

  const onSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSubmitted(true);
    trackCtaClick({
      event: "lead_form_submit",
      location: "company-contact",
      label: "Submit contact form",
    });
  };

  return (
    <form className="space-y-4 rounded-lg border border-slate-200 p-6" onSubmit={onSubmit}>
      <div>
        <label className="mb-1 block text-sm font-medium" htmlFor="name">
          Full name
        </label>
        <input id="name" required className="w-full rounded border border-slate-300 px-3 py-2" />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium" htmlFor="email">
          Work email
        </label>
        <input
          id="email"
          type="email"
          required
          className="w-full rounded border border-slate-300 px-3 py-2"
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium" htmlFor="message">
          How can we help?
        </label>
        <textarea id="message" required rows={4} className="w-full rounded border border-slate-300 px-3 py-2" />
      </div>
      <button
        type="submit"
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500"
      >
        Submit contact form
      </button>
      {submitted ? <p className="text-sm text-emerald-700">Thanks, our team will follow up within 1 business day.</p> : null}
    </form>
  );
}

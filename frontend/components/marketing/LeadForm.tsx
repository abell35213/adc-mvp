"use client";

import { FormEvent, useState } from "react";
import { trackCtaClick } from "@/lib/tracking";

interface LeadFormState {
  name: string;
  email: string;
  message: string;
}

const EMPTY_FORM: LeadFormState = {
  name: "",
  email: "",
  message: "",
};

export default function LeadForm() {
  const [form, setForm] = useState<LeadFormState>(EMPTY_FORM);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSubmitting(true);
    setSubmitError(null);

    try {
      const response = await fetch("/api/leads", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(form),
      });

      if (!response.ok) {
        throw new Error("We could not send your request. Please try again.");
      }

      setSubmitted(true);
      setForm(EMPTY_FORM);
      trackCtaClick({
        event: "lead_form_submit",
        location: "company-contact",
        label: "Submit contact form",
      });
    } catch {
      setSubmitError("We could not send your request. Please try again.");
      setSubmitted(false);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form className="space-y-4 rounded-lg border border-slate-200 p-6" onSubmit={onSubmit}>
      <div>
        <label className="mb-1 block text-sm font-medium" htmlFor="name">
          Full name
        </label>
        <input
          id="name"
          required
          className="w-full rounded border border-slate-300 px-3 py-2"
          value={form.name}
          onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
        />
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
          value={form.email}
          onChange={(event) => setForm((prev) => ({ ...prev, email: event.target.value }))}
        />
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium" htmlFor="message">
          How can we help?
        </label>
        <textarea
          id="message"
          required
          rows={4}
          className="w-full rounded border border-slate-300 px-3 py-2"
          value={form.message}
          onChange={(event) => setForm((prev) => ({ ...prev, message: event.target.value }))}
        />
      </div>
      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:bg-slate-400"
      >
        {isSubmitting ? "Submitting..." : "Submit contact form"}
      </button>
      {submitted ? (
        <p className="text-sm text-emerald-700">Thanks, our team will follow up within 1 business day.</p>
      ) : null}
      {submitError ? <p className="text-sm text-red-700">{submitError}</p> : null}
    </form>
  );
}

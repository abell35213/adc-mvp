"use client";

import { useState, type FormEvent } from "react";
import type { IncidentNoteItem } from "@/lib/api";

interface CaseNotesPanelProps {
  notes: IncidentNoteItem[];
  onAddNote: (body: string) => Promise<void>;
}

export default function CaseNotesPanel({ notes, onAddNote }: CaseNotesPanelProps) {
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!body.trim()) return;
    setBusy(true);
    try {
      await onAddNote(body.trim());
      setBody("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-600">Case notes</h3>
      <form onSubmit={submit} className="mt-3 flex gap-2">
        <input value={body} onChange={(e) => setBody(e.target.value)} placeholder="Add note for handoff or legal context" className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm" />
        <button disabled={busy || !body.trim()} className="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-60">Add</button>
      </form>
      <ul className="mt-3 space-y-2 text-sm">
        {notes.map((note) => (
          <li key={note.note_id} className="rounded-md border border-gray-200 p-2">
            <p className="text-gray-800">{note.body}</p>
          </li>
        ))}
        {notes.length === 0 ? <li className="text-gray-500">No notes yet.</li> : null}
      </ul>
    </section>
  );
}

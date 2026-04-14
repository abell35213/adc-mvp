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
    <div className="rounded-lg border bg-white p-4 shadow dark:bg-gray-800">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-500">Case notes</h3>
      <form onSubmit={submit} className="mt-3 flex gap-2">
        <input
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder="Add note"
          className="flex-1 rounded border px-3 py-2 text-sm dark:border-gray-600 dark:bg-gray-900"
        />
        <button disabled={busy || !body.trim()} className="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-60">
          Add
        </button>
      </form>
      <ul className="mt-3 space-y-2 text-sm">
        {notes.map((note) => (
          <li key={note.note_id} className="rounded border p-2 dark:border-gray-700">
            <p className="text-gray-800 dark:text-gray-200">{note.body}</p>
          </li>
        ))}
        {notes.length === 0 && <li className="text-gray-500">No notes yet.</li>}
      </ul>
    </div>
  );
}

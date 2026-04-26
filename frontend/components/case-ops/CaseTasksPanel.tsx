"use client";

import { useState, type FormEvent } from "react";
import type { IncidentTaskItem } from "@/lib/api";

interface CaseTasksPanelProps {
  tasks: IncidentTaskItem[];
  onAddTask: (title: string) => Promise<void>;
  onCompleteTask: (taskId: string) => Promise<void>;
}

export default function CaseTasksPanel({ tasks, onAddTask, onCompleteTask }: CaseTasksPanelProps) {
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    setBusy(true);
    try {
      await onAddTask(title.trim());
      setTitle("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-lg border bg-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-gray-600">Next action tasks</h3>
      <form onSubmit={submit} className="mt-3 flex gap-2">
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Create next action" className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm" />
        <button disabled={busy || !title.trim()} className="rounded bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-60">Add</button>
      </form>
      <ul className="mt-3 space-y-2 text-sm">
        {tasks.map((task) => (
          <li key={task.task_id} className="flex items-center justify-between rounded-md border border-gray-200 p-2">
            <div>
              <p className="text-gray-800">{task.title}</p>
              <p className="text-xs text-gray-500">{task.status} · {task.priority}</p>
            </div>
            <button
              disabled={task.status !== "open"}
              onClick={() => {
                if (task.status !== "open") return;
                void onCompleteTask(task.task_id);
              }}
              className="rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-50 disabled:opacity-50"
            >
              Complete
            </button>
          </li>
        ))}
        {tasks.length === 0 ? <li className="text-gray-500">No tasks yet.</li> : null}
      </ul>
    </section>
  );
}

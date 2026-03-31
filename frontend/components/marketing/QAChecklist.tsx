type QAChecklistProps = {
  phase: string;
};

const checks = [
  "Mobile (<=640px): hero and CTA stack vertically with no overflow.",
  "Tablet (641px-1024px): cards wrap to two columns and spacing remains consistent.",
  "Desktop (>1024px): content caps at readable max width and CTA remains above the fold.",
];

export default function QAChecklist({ phase }: QAChecklistProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-slate-50 p-4">
      <h2 className="text-lg font-semibold">{phase} QA checklist</h2>
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
        {checks.map((check) => (
          <li key={check}>{check}</li>
        ))}
      </ul>
    </section>
  );
}

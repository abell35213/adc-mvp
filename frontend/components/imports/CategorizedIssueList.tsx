import type { ImportIssue } from "@/lib/csvImport";

type CategorizedIssueListProps = {
  issues: ImportIssue[];
};

export default function CategorizedIssueList({ issues }: CategorizedIssueListProps) {
  const grouped = issues.reduce<Record<string, ImportIssue[]>>((acc, issue) => {
    const key = `${issue.severity}:${issue.category}`;
    if (!acc[key]) acc[key] = [];
    acc[key].push(issue);
    return acc;
  }, {});

  if (issues.length === 0) {
    return <p className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-800">No validation issues found in preview rows.</p>;
  }

  return (
    <div className="space-y-3">
      {Object.entries(grouped).map(([key, values]) => {
        const [severity, category] = key.split(":");
        const isError = severity === "error";
        return (
          <div
            key={key}
            className={`rounded-md border px-3 py-2 ${
              isError
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-amber-200 bg-amber-50 text-amber-800"
            }`}
          >
            <p className="text-sm font-semibold">{isError ? "Errors" : "Warnings"}: {category}</p>
            <ul className="mt-1 list-disc pl-5 text-sm">
              {values.slice(0, 8).map((issue, idx) => (
                <li key={`${issue.message}-${idx}`}>{issue.message}</li>
              ))}
            </ul>
            {values.length > 8 && <p className="mt-1 text-xs">+{values.length - 8} more in this category.</p>}
          </div>
        );
      })}
    </div>
  );
}

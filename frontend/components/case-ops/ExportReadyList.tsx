import Link from "next/link";
import SectionCard from "@/components/layout/SectionCard";
import type { CaseOpsQueueItem } from "@/lib/api";

interface ExportReadyListProps {
  items: CaseOpsQueueItem[];
  loading: boolean;
}

export default function ExportReadyList({ items, loading }: ExportReadyListProps) {
  return (
    <SectionCard
      title="Ready for Export"
      tone="success"
      description="Cases cleared for export once QA is complete."
    >
      {loading && <p className="text-sm text-text-secondary">Loading export-ready incidents…</p>}
      {!loading && items.length === 0 && (
        <p className="text-sm text-text-secondary">No incidents are ready for export.</p>
      )}
      {!loading && items.length > 0 && (
        <ul className="space-y-2 text-sm">
          {items.slice(0, 6).map((item) => (
            <li key={item.incident_id} className="rounded-md border border-border-subtle bg-surface-raised px-3 py-2">
              <Link href={`/incidents/${item.incident_id}`} className="font-medium text-status-success hover:underline">
                {item.incident_id.slice(0, 8)}…
              </Link>
              <p className="text-xs text-text-secondary">
                Completeness {Math.round(item.completeness_percent)}% · Owner {item.owner_user_id ? item.owner_user_id.slice(0, 8) : "unassigned"}
              </p>
            </li>
          ))}
        </ul>
      )}
    </SectionCard>
  );
}

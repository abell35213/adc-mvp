"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import MainLayout from "@/components/MainLayout";
import { Alert, Button, Card, CardContent, EmptyState, FormField, Input, Select, Skeleton, StatusBadge } from "@/components/ui";
import { listEvidence, toUserErrorMessage, type EvidenceInventoryItem } from "@/lib/api";

export default function EvidencePage() {
  const [items, setItems] = useState<EvidenceInventoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState("");
  const [type, setType] = useState("");
  const [search, setSearch] = useState("");
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const response = await listEvidence({
        page,
        page_size: pageSize,
        status: status || undefined,
        artifact_type: type || undefined,
        search: search || undefined,
      });
      setItems(response.items);
      setPage(response.page);
      setPageSize(response.page_size);
      setTotal(response.total);
    }
    catch (err) { setError(toUserErrorMessage(err, "Evidence inventory could not be loaded.")); }
    finally { setLoading(false); }
  }, [page, pageSize, search, status, type]);
  useEffect(() => { void load(); }, [load]);
  const types = useMemo(() => [...new Set(items.map((item) => item.artifact_type))].sort(), [items]);
  const captured = items.filter((item) => item.status === "captured").length;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const pageStart = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const pageEnd = total === 0 ? 0 : Math.min(total, page * pageSize);
  return <MainLayout title="Evidence"><div className="space-y-6">
    <div><h1 className="text-3xl font-semibold text-text-primary">Evidence</h1><p className="mt-2 text-sm text-text-secondary">Organization evidence inventory loaded through one paginated request.</p></div>
    <div className="grid gap-3 sm:grid-cols-3"><Card><CardContent><p className="text-sm text-text-secondary">Visible</p><p className="text-3xl font-semibold">{items.length}</p></CardContent></Card><Card><CardContent><p className="text-sm text-text-secondary">Captured</p><p className="text-3xl font-semibold">{captured}</p></CardContent></Card><Card><CardContent><p className="text-sm text-text-secondary">Needs attention</p><p className="text-3xl font-semibold">{items.length-captured}</p></CardContent></Card></div>
    <Card><CardContent className="grid gap-3 md:grid-cols-3"><FormField id="evidence-search" label="Case or evidence search"><Input id="evidence-search" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} /></FormField><FormField id="evidence-status" label="Status"><Select id="evidence-status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}><option value="">All statuses</option><option value="captured">Captured</option><option value="pending">Pending</option><option value="unavailable">Unavailable</option></Select></FormField><FormField id="evidence-type" label="Evidence type"><Select id="evidence-type" value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}><option value="">All types</option>{types.map((value) => <option key={value}>{value}</option>)}</Select></FormField></CardContent></Card>
    {error ? <Alert tone="critical" title="Evidence request failed" description={error}><Button onClick={() => void load()}>Retry</Button></Alert> : null}
    {loading ? <div className="space-y-2"><Skeleton className="h-20"/><Skeleton className="h-20"/></div> : items.length === 0 ? <EmptyState title="No evidence matches these filters" message="Adjust the filters or retry the inventory request."/> : <div className="grid gap-3">{items.map((item) => <Card key={item.artifact_id}><CardContent className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center"><div><p className="font-medium text-text-primary">{item.artifact_type.replaceAll("_", " ")}</p><p className="text-sm text-text-secondary">{item.case_reference} · {item.source}</p>{item.detail ? <p className="text-xs text-text-muted">{item.detail}</p> : null}</div><div className="flex items-center gap-3"><StatusBadge tone={item.status === "captured" ? "success" : item.status === "unavailable" ? "critical" : "warning"}>{item.status}</StatusBadge><Link className="cursor-pointer text-sm text-text-link hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus-ring" href={`/incidents/${item.incident_id}`}>Open case</Link></div></CardContent></Card>)}</div>}
    <Card><CardContent className="flex flex-col gap-3 text-sm text-text-secondary sm:flex-row sm:items-center sm:justify-between"><p>{total === 0 ? "No evidence results" : `Showing ${pageStart}-${pageEnd} of ${total} evidence items`}</p><div className="flex items-center gap-2"><span>Page {page} of {totalPages}</span><Button variant="secondary" onClick={() => setPage((current) => current - 1)} disabled={loading || page <= 1}>Previous</Button><Button variant="secondary" onClick={() => setPage((current) => current + 1)} disabled={loading || page >= totalPages}>Next</Button></div></CardContent></Card>
  </div></MainLayout>;
}

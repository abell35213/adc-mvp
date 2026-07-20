"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import MainLayout from "@/components/MainLayout";
import { Alert, Button, Card, CardContent, CardHeader, Drawer, EmptyState, FormField, Input, MetricCard, Select, Skeleton, StatusBadge } from "@/components/ui";
import { DocumentExportList } from "@/components/exports/DocumentExportList";
import { downloadExport, getExport, getExportContents, getExportDownloadHistory, listExports, retryExport, type ExportContentsItem, type ExportDownloadAuditResponse, type ExportListItem as ExportItem, type ExportStatus, type ExportSummary, toUserErrorMessage } from "@/lib/api";
import { safeOpenDownloadUrl } from "@/lib/safeUrl";
import { EXPORT_STATUS_OPTIONS } from "@/lib/status";
import { buildExportDocumentViewModel, formatBytes, formatDateTime, sortExportDocuments } from "@/lib/exportDocuments";
import { countExportQuickFilters, filterExportDocuments } from "@/lib/exportQuickFilters.mjs";

type ExportQuickFilter = "ready" | "generating" | "attention" | "completedThisWeek";

function initialParam(name: string) { return typeof window === "undefined" ? "" : new URLSearchParams(window.location.search).get(name) ?? ""; }

export default function ExportsPage() {
  const router = useRouter();
  const [exports, setExports] = useState<ExportItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState(() => initialParam("search"));
  const [status, setStatus] = useState<"all" | ExportStatus>(() => (initialParam("status") || "all") as "all" | ExportStatus);
  const [sort, setSort] = useState(() => initialParam("sort") || "priority");
  const [quickFilter, setQuickFilter] = useState<ExportQuickFilter | null>(() => (initialParam("quick") || null) as ExportQuickFilter | null);
  const [selectedExportId, setSelectedExportId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ExportSummary | null>(null);
  const [contents, setContents] = useState<ExportContentsItem[] | null>(null);
  const [audit, setAudit] = useState<ExportDownloadAuditResponse | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  async function refresh() { const data = await listExports(); setExports(data); }
  useEffect(() => { refresh().catch((err) => setError(toUserErrorMessage(err, "Documents could not be loaded."))).finally(() => setLoading(false)); }, []);
  useEffect(() => { const params = new URLSearchParams(); if (query) params.set("search", query); if (status !== "all") params.set("status", status); if (sort !== "priority") params.set("sort", sort); if (quickFilter) params.set("quick", quickFilter); router.replace(params.size ? `/exports?${params}` : "/exports", { scroll: false }); }, [query, quickFilter, router, sort, status]);

  const filtered = useMemo(() => {
    const base = filterExportDocuments(exports, { status, query, quickFilter, getSearchText: (item) => buildExportDocumentViewModel(item).searchText });
    if (sort === "newest") return [...base].sort((a, b) => new Date(b.created_at_utc ?? 0).getTime() - new Date(a.created_at_utc ?? 0).getTime());
    if (sort === "oldest") return [...base].sort((a, b) => new Date(a.created_at_utc ?? 0).getTime() - new Date(b.created_at_utc ?? 0).getTime());
    if (sort === "type") return [...base].sort((a, b) => buildExportDocumentViewModel(a).typeLabel.localeCompare(buildExportDocumentViewModel(b).typeLabel));
    if (sort === "case") return [...base].sort((a, b) => buildExportDocumentViewModel(a).caseReference.localeCompare(buildExportDocumentViewModel(b).caseReference));
    return sortExportDocuments(base);
  }, [exports, query, quickFilter, sort, status]);

  const counts = useMemo(() => countExportQuickFilters(exports), [exports]);
  const activeFilters = (query ? 1 : 0) + (status !== "all" ? 1 : 0) + (quickFilter ? 1 : 0);
  const toggleQuickFilter = (next: ExportQuickFilter) => setQuickFilter((current: ExportQuickFilter | null) => current === next ? null : next);

  function blockedMessage(url: string) { try { return `Download URL from unrecognized host "${new URL(url).host}" was blocked.`; } catch { return "Download URL from an unrecognized host was blocked."; } }
  async function handleDetails(exportId: string) { setDetailLoading(true); setSelectedExportId(exportId); setDetail(null); setContents(null); setAudit(null); try { const [d, c, a] = await Promise.all([getExport(exportId), getExportContents(exportId), getExportDownloadHistory(exportId)]); setDetail(d); setContents(c.file_manifest); setAudit(a); } catch (err) { setError(toUserErrorMessage(err, "Document details could not be loaded.")); } finally { setDetailLoading(false); } }
  async function handleRetry(exportId: string) { setBusyId(exportId); setError(""); try { await retryExport(exportId); await refresh(); } catch (err) { setError(toUserErrorMessage(err, "Retry could not be started.")); } finally { setBusyId(null); } }
  async function handleDownload(exportId: string) { setBusyId(exportId); setError(""); try { const result = await downloadExport(exportId); if (!safeOpenDownloadUrl(result.url)) setError(blockedMessage(result.url)); } catch (err) { setError(toUserErrorMessage(err, "Document could not be downloaded.")); } finally { setBusyId(null); } }

  const selectedVm = detail ? buildExportDocumentViewModel(detail) : null;
  return <MainLayout title="Exports & Documents"><div className="space-y-6"><div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><h1 className="text-3xl font-semibold tracking-tight text-text-primary">Exports &amp; Documents</h1><p className="mt-2 text-sm text-text-secondary">Generate, monitor, and download defense-ready case materials.</p></div><Button variant="secondary" onClick={() => setError("Open a case Documents tab to generate a document with incident context.")}>Generate Document</Button></div>
    <div className="grid gap-3 md:grid-cols-4" aria-label="Document quick filters">{loading ? [0,1,2,3].map((i) => <Skeleton key={i} className="h-28"/>) : <><MetricCard label="Ready to Download" value={counts.ready} onClick={() => toggleQuickFilter("ready")} pressed={quickFilter === "ready"}/><MetricCard label="Generating" value={counts.generating} onClick={() => toggleQuickFilter("generating")} pressed={quickFilter === "generating"}/><MetricCard label="Needs Attention" value={counts.attention} onClick={() => toggleQuickFilter("attention")} pressed={quickFilter === "attention"}/><MetricCard label="Completed This Week" value={counts.completedThisWeek} onClick={() => toggleQuickFilter("completedThisWeek")} pressed={quickFilter === "completedThisWeek"}/></>}</div>
    <p className="sr-only" role="status" aria-live="polite">{quickFilter ? `${filtered.length} documents match the selected quick filter and search.` : ""}</p>
    <Card><CardContent className="grid gap-3 md:grid-cols-[1fr_180px_180px_auto]"><FormField id="document-search" label="Search"><Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Document, case, file, or type" /></FormField><FormField id="document-status" label="Status"><Select value={status} onChange={(e) => setStatus(e.target.value as typeof status)}><option value="all">All statuses</option>{EXPORT_STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</Select></FormField><FormField id="document-sort" label="Sort"><Select value={sort} onChange={(e) => setSort(e.target.value)}><option value="priority">Operational priority</option><option value="newest">Newest</option><option value="oldest">Oldest</option><option value="case">Case</option><option value="type">Document type</option></Select></FormField><div className="flex items-end"><Button variant="quiet" onClick={() => { setQuery(""); setStatus("all"); setQuickFilter(null); }} disabled={!activeFilters}>Clear filters{activeFilters ? ` (${activeFilters})` : ""}</Button></div></CardContent></Card>
    {error ? <Alert tone="critical" title="Document workflow needs attention" description={error}/> : null}
    {loading ? <div className="space-y-2"><Skeleton className="h-16"/><Skeleton className="h-16"/><Skeleton className="h-16"/></div> : filtered.length === 0 ? <EmptyState title={exports.length ? "No documents match these filters" : "No documents yet"} message={exports.length ? "Clear filters or select another document status." : "Open an incident Documents tab to generate the first defense-ready case document."}/> : <DocumentExportList items={filtered} onDownload={handleDownload} onRetry={handleRetry} onDetails={handleDetails} busyId={busyId}/>} 
    <Drawer open={Boolean(selectedExportId)} onClose={() => setSelectedExportId(null)} title={selectedVm?.title ?? "Document details"} description={selectedVm?.caseReference}>{detailLoading ? <div className="space-y-3"><Skeleton className="h-24"/><Skeleton className="h-48"/></div> : detail && selectedVm ? <div className="space-y-4"><div className="flex items-start justify-between gap-3"><div><p className="text-sm text-text-secondary">{selectedVm.typeLabel}</p><p className="text-xs text-text-muted">{selectedVm.fileMeta}</p></div><StatusBadge tone={selectedVm.statusTone}>{selectedVm.statusLabel}</StatusBadge></div><Alert tone={selectedVm.statusTone === "critical" ? "critical" : "informational"} title={selectedVm.statusDescription} description={selectedVm.safeFailureReason ?? selectedVm.stageLabel}/><Card><CardHeader title="Case context"/><CardContent><p className="text-sm text-text-secondary">{selectedVm.caseReference} · {selectedVm.incidentContext}</p></CardContent></Card>{selectedVm.missingRequirements.length ? <Card><CardHeader title="Requirements / missing information"/><CardContent><ul className="list-disc pl-5 text-sm text-text-secondary">{selectedVm.missingRequirements.map((m) => <li key={m}>{m}</li>)}</ul></CardContent></Card> : null}<Card><CardHeader title="File details"/><CardContent><dl className="grid gap-2 text-sm text-text-secondary"><div>File: {selectedVm.fileMeta}</div><div>Generated: {selectedVm.generatedLabel}</div><div>Expires: {formatDateTime(detail.expires_at_utc)}</div><div>Artifacts: {detail.artifact_count}</div><div>Timeline events: {detail.timeline_event_count}</div></dl></CardContent></Card><Card><CardHeader title="Generation history"/><CardContent><ul className="space-y-2 text-sm text-text-secondary"><li>Requested {formatDateTime(detail.requested_at_utc ?? detail.created_at_utc)}</li>{detail.processing_started_at_utc ? <li>Started {formatDateTime(detail.processing_started_at_utc)}</li> : null}{detail.completed_at_utc ? <li>Completed {formatDateTime(detail.completed_at_utc)}</li> : null}{audit?.downloads.map((event, idx) => <li key={`${event.occurred_at_utc}-${idx}`}>Downloaded {formatDateTime(event.occurred_at_utc)}</li>)}</ul></CardContent></Card>{contents ? <Card><CardHeader title="Document contents"/><CardContent><ul className="space-y-2 text-sm text-text-secondary">{contents.map((item) => <li key={`${item.kind}-${item.path ?? item.item}`}>{item.item ?? item.kind} · {item.classification} · {formatBytes(item.byte_size)}</li>)}</ul></CardContent></Card> : null}<details className="rounded-lg border border-border-subtle p-3 text-xs text-text-secondary"><summary className="cursor-pointer font-medium text-text-primary">Technical details</summary><dl className="mt-3 space-y-2"><div>Export ID: <span className="font-mono">{detail.export_id}</span></div><div>Incident ID: <span className="font-mono">{detail.incident_id}</span></div><div>Status: {detail.status}</div><div>Stage: {detail.progress_stage}</div><div>SHA256: {detail.package_sha256 ?? "—"}</div></dl></details></div> : null}</Drawer>
  </div></MainLayout>;
}

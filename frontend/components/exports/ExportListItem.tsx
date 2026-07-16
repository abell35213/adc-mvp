"use client";

import type { ExportSummary } from "@/lib/api";
import { DocumentExportList } from "./DocumentExportList";

interface ExportListItemProps { 
  item: ExportSummary; 
  showIncident?: boolean; 
  onDownload: (exportId: string) => void;
  onRetry: (exportId: string) => void; 
  onDetails?: (exportId: string) => void;
}

export default function ExportListItem({ 
  item, 
  showIncident = false, 
  onDownload, 
  onRetry, 
  onDetails,
}: ExportListItemProps) { 
  return (
    <DocumentExportList 
      items={[item]}
      showIncident={showIncident}
      onDownload={onDownload}
      onRetry={onRetry} 
      {...(onDetails ? { onDetails } : {})}
    />
  );
}


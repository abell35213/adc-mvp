export type ImportIssueSeverity = "error" | "warning";

export interface ImportIssue {
  severity: ImportIssueSeverity;
  category: string;
  message: string;
  rowIndex?: number;
}

export interface ParsedCsv {
  headers: string[];
  rows: string[][];
}

export function parseCsv(content: string): ParsedCsv {
  const rows: string[][] = [];
  let currentRow: string[] = [];
  let currentCell = "";
  let inQuotes = false;

  for (let i = 0; i < content.length; i += 1) {
    const char = content[i];
    const next = content[i + 1];

    if (char === '"') {
      if (inQuotes && next === '"') {
        currentCell += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }

    if (!inQuotes && char === ",") {
      currentRow.push(currentCell.trim());
      currentCell = "";
      continue;
    }

    if (!inQuotes && (char === "\n" || char === "\r")) {
      if (char === "\r" && next === "\n") i += 1;
      currentRow.push(currentCell.trim());
      if (currentRow.some((cell) => cell.length > 0)) {
        rows.push(currentRow);
      }
      currentRow = [];
      currentCell = "";
      continue;
    }

    currentCell += char;
  }

  if (currentCell.length > 0 || currentRow.length > 0) {
    currentRow.push(currentCell.trim());
    if (currentRow.some((cell) => cell.length > 0)) {
      rows.push(currentRow);
    }
  }

  if (rows.length === 0) return { headers: [], rows: [] };
  const [headers, ...dataRows] = rows;
  return { headers, rows: dataRows };
}

export function normalizeHeader(header: string): string {
  return header.trim().toLowerCase().replace(/[^a-z0-9_]/g, "");
}

export function autoMapHeaders(
  headers: string[],
  aliases: Record<string, string[]>
): Record<string, string> {
  const normalizedToOriginal = new Map(headers.map((h) => [normalizeHeader(h), h]));
  const mapping: Record<string, string> = {};

  Object.entries(aliases).forEach(([canonical, values]) => {
    for (const value of values) {
      const found = normalizedToOriginal.get(normalizeHeader(value));
      if (found) {
        mapping[canonical] = found;
        break;
      }
    }
  });

  return mapping;
}

function cell(row: Record<string, string>, key?: string): string {
  if (!key) return "";
  return (row[key] ?? "").trim();
}

export function buildRowObjects(headers: string[], rows: string[][]): Record<string, string>[] {
  return rows.map((raw) => {
    const out: Record<string, string> = {};
    headers.forEach((header, i) => {
      out[header] = raw[i] ?? "";
    });
    return out;
  });
}

export interface VehiclePreviewRow {
  unitNumber: string;
  vin: string;
  providerVehicleId: string;
  isActive: string;
}

export interface DriverPreviewRow {
  firstName: string;
  lastName: string;
  phone: string;
  providerDriverId: string;
  isActive: string;
}

export function buildVehiclePreview(
  rows: Record<string, string>[],
  mapping: Record<string, string>
): { previewRows: VehiclePreviewRow[]; issues: ImportIssue[] } {
  const issues: ImportIssue[] = [];
  const seen = new Set<string>();

  const previewRows = rows.map((row, index) => {
    const unit = cell(row, mapping.unit_number);
    const vin = cell(row, mapping.vin);
    const providerVehicleId = cell(row, mapping.provider_vehicle_id);
    const isActive = cell(row, mapping.is_active) || "true";

    if (!unit) {
      issues.push({ severity: "error", category: "Required fields", message: `Row ${index + 2}: unit number is required`, rowIndex: index });
    }
    const key = unit.toLowerCase();
    if (unit && seen.has(key)) {
      issues.push({ severity: "error", category: "Duplicate values", message: `Row ${index + 2}: duplicate unit number '${unit}'`, rowIndex: index });
    }
    if (unit) seen.add(key);

    if (!vin) {
      issues.push({ severity: "warning", category: "Data completeness", message: `Row ${index + 2}: VIN is missing`, rowIndex: index });
    }

    return { unitNumber: unit, vin, providerVehicleId, isActive };
  });

  if (!mapping.unit_number) {
    issues.unshift({ severity: "error", category: "Column mapping", message: "No column mapped to unit number." });
  }

  return { previewRows, issues };
}

const PHONE_RE = /^\+?[1-9]\d{7,14}$/;

export function buildDriverPreview(
  rows: Record<string, string>[],
  mapping: Record<string, string>
): { previewRows: DriverPreviewRow[]; issues: ImportIssue[] } {
  const issues: ImportIssue[] = [];
  const seenPhones = new Set<string>();

  const previewRows = rows.map((row, index) => {
    const firstName = cell(row, mapping.first_name);
    const lastName = cell(row, mapping.last_name);
    const phone = cell(row, mapping.phone);
    const providerDriverId = cell(row, mapping.provider_driver_id);
    const isActive = cell(row, mapping.is_active) || "true";

    if (!firstName || !lastName || !phone) {
      issues.push({ severity: "error", category: "Required fields", message: `Row ${index + 2}: first name, last name, and phone are required`, rowIndex: index });
    }

    if (phone && !PHONE_RE.test(phone.replace(/[\s()-]/g, ""))) {
      issues.push({ severity: "warning", category: "Phone formatting", message: `Row ${index + 2}: phone may not be in E.164 format`, rowIndex: index });
    }

    const key = phone.toLowerCase();
    if (phone && seenPhones.has(key)) {
      issues.push({ severity: "error", category: "Duplicate values", message: `Row ${index + 2}: duplicate phone '${phone}'`, rowIndex: index });
    }
    if (phone) seenPhones.add(key);

    return { firstName, lastName, phone, providerDriverId, isActive };
  });

  if (!mapping.phone) {
    issues.unshift({ severity: "error", category: "Column mapping", message: "No column mapped to phone." });
  }

  return { previewRows, issues };
}

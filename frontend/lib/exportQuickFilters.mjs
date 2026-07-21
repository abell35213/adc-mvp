export const EXPORT_QUICK_FILTERS = {
  ready: { label: "Ready to Download", statuses: ["ready"] },
  generating: { label: "Generating", statuses: ["requested", "queued", "processing"] },
  attention: { label: "Needs Attention", statuses: ["failed", "expired"] },
  completedThisWeek: { label: "Completed This Week", statuses: ["ready"] },
};

export function startOfCurrentWeek(now = new Date()) {
  const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const daySinceMonday = (start.getUTCDay() + 6) % 7;
  start.setUTCDate(start.getUTCDate() - daySinceMonday);
  return start;
}

/** @param {Record<string, any>} item @param {string | null} filter @param {Date} now */
export function matchesExportQuickFilter(item, filter, now = new Date()) {
  if (!filter) return true;
  const definition = EXPORT_QUICK_FILTERS[filter];
  if (!definition?.statuses.includes(item.status)) return false;
  if (filter !== "completedThisWeek") return true;
  if (!item.completed_at_utc) return false;
  const completed = new Date(item.completed_at_utc);
  return !Number.isNaN(completed.getTime()) && completed >= startOfCurrentWeek(now) && completed <= now;
}

/**
 * @template T
 * @param {T[]} items
 * @param {{status?: string, query?: string, quickFilter?: string | null, now?: Date, getSearchText?: (item: T) => string}} options
 */
export function filterExportDocuments(items, { status = "all", query = "", quickFilter = null, now = new Date(), getSearchText = (item) => item.searchText ?? "" } = {}) {
  const normalizedQuery = query.trim().toLowerCase();
  return items.filter((item) =>
    (status === "all" || item.status === status) &&
    matchesExportQuickFilter(item, quickFilter, now) &&
    (!normalizedQuery || getSearchText(item).toLowerCase().includes(normalizedQuery)),
  );
}

/** @param {Record<string, any>[]} items @param {Date} now */
export function countExportQuickFilters(items, now = new Date()) {
  return Object.fromEntries(Object.keys(EXPORT_QUICK_FILTERS).map((key) => [key, items.filter((item) => matchesExportQuickFilter(item, key, now)).length]));
}

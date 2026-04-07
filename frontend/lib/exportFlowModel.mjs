export function nextModalStep(step, action) {
  if (action === 'close' || action === 'submit_success') return 'configure';
  if (action === 'toggle_review') return step === 'configure' ? 'review' : 'configure';
  return step;
}

export function derivePollingState({ status, stage, activeExportId }) {
  const polling = Boolean(activeExportId) && ['requested', 'queued', 'processing'].includes(status);
  return {
    polling,
    stageText: stage ?? 'Starting export workflow',
  };
}

export function deriveReadyActions(readyExport) {
  return {
    showReadyCard: Boolean(readyExport),
    canDownload: Boolean(readyExport?.export_id),
  };
}

export function deriveDetailVisibility({ status, errorMessage, exportsCount }) {
  return {
    showFailedState: status === 'failed' || status === 'expired',
    showErrorInline: Boolean(errorMessage) && status !== 'failed' && status !== 'expired',
    showEmptyState: exportsCount === 0,
  };
}

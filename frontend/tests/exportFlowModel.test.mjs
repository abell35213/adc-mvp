import test from 'node:test';
import assert from 'node:assert/strict';
import {
  nextModalStep,
  derivePollingState,
  deriveReadyActions,
  deriveDetailVisibility,
} from '../lib/exportFlowModel.mjs';

test('modal flow transitions configure -> review -> configure and resets on close', () => {
  assert.equal(nextModalStep('configure', 'toggle_review'), 'review');
  assert.equal(nextModalStep('review', 'toggle_review'), 'configure');
  assert.equal(nextModalStep('review', 'close'), 'configure');
  assert.equal(nextModalStep('review', 'submit_success'), 'configure');
});

test('polling states include queued and processing when active export id exists', () => {
  assert.deepEqual(
    derivePollingState({ status: 'queued', stage: 'request_accepted', activeExportId: 'exp-1' }),
    { polling: true, stageText: 'request_accepted' },
  );

  assert.deepEqual(
    derivePollingState({ status: 'ready', stage: 'ready_for_download', activeExportId: 'exp-1' }),
    { polling: false, stageText: 'ready_for_download' },
  );
});

test('ready/download actions are available only for a ready export id', () => {
  assert.deepEqual(deriveReadyActions(null), { showReadyCard: false, canDownload: false });
  assert.deepEqual(
    deriveReadyActions({ export_id: 'exp-2', package_sha256: 'abc' }),
    { showReadyCard: true, canDownload: true },
  );
});

test('detail visibility toggles failed and inline error paths', () => {
  assert.deepEqual(
    deriveDetailVisibility({ status: 'failed', errorMessage: 'boom', exportsCount: 1 }),
    { showFailedState: true, showErrorInline: false, showEmptyState: false },
  );
  assert.deepEqual(
    deriveDetailVisibility({ status: 'processing', errorMessage: 'temporary', exportsCount: 2 }),
    { showFailedState: false, showErrorInline: true, showEmptyState: false },
  );
});

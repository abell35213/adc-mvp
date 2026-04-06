import { useCallback, useEffect, useState } from 'react';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Button, HelperText, Text, TextInput } from 'react-native-paper';
import * as SecureStore from 'expo-secure-store';

import {
  DriverNarrativePayload,
  getDriverActiveIncident,
  patchDriverIncidentNarrative,
} from '../api';
import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import { emitProtocolAnalyticsEvent } from '../telemetry/protocolEvents';

type Props = NativeStackScreenProps<RootStackParamList, 'Narrative'>;

type CompletionState = 'draft' | 'completed';

type NarrativeDraft = {
  narrativeText: string;
  completionState: CompletionState;
};

type StoredNarrativeDraft = {
  incidentId: string | null;
  draft: NarrativeDraft;
};

const STORAGE_KEY = 'driver_narrative_draft_v1';

const EMPTY_DRAFT: NarrativeDraft = {
  narrativeText: '',
  completionState: 'draft',
};

function buildNarrativePayload(draft: NarrativeDraft): DriverNarrativePayload {
  return {
    narrative_text: draft.narrativeText.trim(),
    completion_state: draft.completionState,
  };
}

export default function NarrativeScreen({ navigation }: Props) {
  const { completeRoute, protocolContext } = useProtocolFlow();
  useProtocolRouteGuard('Narrative', navigation);

  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [draft, setDraft] = useState<NarrativeDraft>(EMPTY_DRAFT);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  const persistDraft = useCallback(
    async (nextDraft: NarrativeDraft, currentIncidentId: string | null) => {
      const payload: StoredNarrativeDraft = {
        incidentId: currentIncidentId,
        draft: nextDraft,
      };

      await SecureStore.setItemAsync(STORAGE_KEY, JSON.stringify(payload));

      const trimmedIncidentId = currentIncidentId?.trim();
      if (trimmedIncidentId) {
        try {
          await patchDriverIncidentNarrative(trimmedIncidentId, buildNarrativePayload(nextDraft));
        } catch {
          // Keep local draft as source of truth if server sync is unavailable.
        }
      }

    },
    [],
  );

  useEffect(() => {
    const initializeDraft = async () => {
      try {
        const [activeIncident, storedRaw] = await Promise.all([
          getDriverActiveIncident(),
          SecureStore.getItemAsync(STORAGE_KEY),
        ]);

        const nextIncidentId = activeIncident?.incident_id ?? null;
        setIncidentId(nextIncidentId);

        if (!storedRaw) {
          return;
        }

        const stored = JSON.parse(storedRaw) as StoredNarrativeDraft;
        if (!stored?.draft) {
          return;
        }

        if (stored.incidentId && nextIncidentId && stored.incidentId !== nextIncidentId) {
          return;
        }

        setDraft({
          ...EMPTY_DRAFT,
          ...stored.draft,
        });
      } catch {
        // Non-blocking.
      } finally {
        setIsInitializing(false);
      }
    };

    void initializeDraft();
  }, []);

  const handleSaveDraft = useCallback(async () => {
    setErrorText(null);
    setIsSaving(true);

    try {
      const nextDraft: NarrativeDraft = {
        ...draft,
        completionState: 'draft',
      };

      await persistDraft(nextDraft, incidentId);
      setDraft(nextDraft);
    } finally {
      setIsSaving(false);
    }
  }, [draft, incidentId, persistDraft]);

  const handleContinue = useCallback(async () => {
    const trimmedNarrative = draft.narrativeText.trim();
    if (!trimmedNarrative) {
      setErrorText('Narrative is required before continuing.');
      return;
    }

    setErrorText(null);
    setIsSaving(true);

    try {
      const nextDraft: NarrativeDraft = {
        narrativeText: trimmedNarrative,
        completionState: 'completed',
      };

      await persistDraft(nextDraft, incidentId);
      setDraft(nextDraft);
      emitProtocolAnalyticsEvent('narrative_saved', {
        incidentId,
        workflowCorrelationId: protocolContext.workflowCorrelationId,
      });
      completeRoute('Narrative');
      navigation.navigate('ReviewSubmit');
    } finally {
      setIsSaving(false);
    }
  }, [
    completeRoute,
    draft.narrativeText,
    incidentId,
    navigation,
    persistDraft,
    protocolContext.workflowCorrelationId,
  ]);

  if (isInitializing) {
    return (
      <View style={styles.stateContainer}>
        <Text variant="bodyLarge">Loading narrative…</Text>
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.headerBlock}>
        <Text variant="headlineSmall">Narrative</Text>
        <Text variant="bodyMedium" style={styles.description}>
          Write a factual, first-hand summary. Do not guess or include assumptions.
        </Text>
      </View>

      <View style={styles.guidanceBlock}>
        <Text variant="titleMedium">Prompt guidance</Text>
        <Text variant="bodySmall" style={styles.guidanceText}>
          • What you directly observed in chronological order
        </Text>
        <Text variant="bodySmall" style={styles.guidanceText}>
          • Who said what, only if you heard it yourself
        </Text>
        <Text variant="bodySmall" style={styles.guidanceText}>
          • Visible conditions (weather, traffic, road hazards)
        </Text>
        <Text variant="bodySmall" style={styles.guidanceText}>
          • Unknown details should be written as “unknown”
        </Text>
      </View>

      <TextInput
        mode="outlined"
        label="Narrative"
        value={draft.narrativeText}
        onChangeText={(value) => setDraft((previous) => ({ ...previous, narrativeText: value }))}
        multiline
        numberOfLines={8}
        placeholder="Describe the incident based only on what you observed."
      />

      {errorText ? <HelperText type="error">{errorText}</HelperText> : null}
      {!errorText && !draft.narrativeText.trim() ? (
        <HelperText type="info">Narrative text is required to mark this step complete.</HelperText>
      ) : null}

      <View style={styles.actions}>
        <Button mode="outlined" onPress={() => navigation.goBack()} disabled={isSaving}>
          Back
        </Button>
        <Button mode="outlined" onPress={() => void handleSaveDraft()} loading={isSaving}>
          Save draft
        </Button>
        <Button mode="contained" onPress={() => void handleContinue()} loading={isSaving}>
          Narrative complete
        </Button>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    gap: 16,
    padding: 24,
  },
  stateContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  headerBlock: {
    gap: 6,
  },
  description: {
    color: '#5f6b7a',
  },
  guidanceBlock: {
    gap: 6,
  },
  guidanceText: {
    color: '#334155',
  },
  actions: {
    marginTop: 'auto',
    gap: 12,
  },
});

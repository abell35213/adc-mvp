import { useCallback, useEffect, useMemo, useState } from 'react';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Button, HelperText, Text, TextInput } from 'react-native-paper';
import AsyncStorage from '@react-native-async-storage/async-storage';

import {
  DriverIncidentPartiesPayload,
  DriverPartyPayload,
  getDriverActiveIncident,
  patchDriverIncidentParties,
} from '../api';
import { MediaPromptType, RootStackParamList } from '../navigation/types';
import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import { emitProtocolAnalyticsEvent } from '../telemetry/protocolEvents';

type Props = NativeStackScreenProps<RootStackParamList, 'ThirdPartyInfo'>;

type ThirdPartyDraftItem = {
  fullName: string;
  phoneNumber: string;
  vehicleDescription: string;
  insurerName: string;
  policyNumber: string;
  notes: string;
};

type CompletionState = 'completed' | 'skipped';

type ThirdPartyDraft = {
  parties: ThirdPartyDraftItem[];
  completionState: CompletionState;
};

type StoredThirdPartyDraft = {
  incidentId: string | null;
  draft: ThirdPartyDraft;
};

const STORAGE_KEY = 'driver_third_party_info_draft_v1';
const UNKNOWN_TOKEN = 'unknown';

const EMPTY_PARTY: ThirdPartyDraftItem = {
  fullName: '',
  phoneNumber: '',
  vehicleDescription: '',
  insurerName: '',
  policyNumber: '',
  notes: '',
};

const EMPTY_DRAFT: ThirdPartyDraft = {
  parties: [{ ...EMPTY_PARTY }],
  completionState: 'completed',
};

function normalizeOptionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

function buildPartyPayload(item: ThirdPartyDraftItem): DriverPartyPayload {
  return {
    full_name: normalizeOptionalText(item.fullName),
    phone_number: normalizeOptionalText(item.phoneNumber),
    vehicle_description: normalizeOptionalText(item.vehicleDescription),
    insurer_name: normalizeOptionalText(item.insurerName),
    policy_number: normalizeOptionalText(item.policyNumber),
    notes: normalizeOptionalText(item.notes),
  };
}

function buildPartiesPayload(draft: ThirdPartyDraft): DriverIncidentPartiesPayload {
  const normalizedParties = draft.parties
    .map(buildPartyPayload)
    .filter((party) => Object.values(party).some((value) => value != null));

  return {
    completion_state: draft.completionState,
    parties: normalizedParties,
  };
}

function hasPartyData(item: ThirdPartyDraftItem): boolean {
  return Object.values(item).some((value) => value.trim().length > 0);
}

export default function ThirdPartyInfoScreen({ navigation }: Props) {
  const { completeRoute, protocolContext } = useProtocolFlow();
  useProtocolRouteGuard('ThirdPartyInfo', navigation);

  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ThirdPartyDraft>(EMPTY_DRAFT);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  const persistDraft = useCallback(
    async (nextDraft: ThirdPartyDraft, currentIncidentId: string | null) => {
      const payload: StoredThirdPartyDraft = {
        incidentId: currentIncidentId,
        draft: nextDraft,
      };

      await AsyncStorage.setItem(STORAGE_KEY, JSON.stringify(payload));

      const trimmedIncidentId = currentIncidentId?.trim();
      if (trimmedIncidentId) {
        try {
          await patchDriverIncidentParties(trimmedIncidentId, buildPartiesPayload(nextDraft));
        } catch {
          // Keep local draft as source of truth if backend sync is unavailable.
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
          AsyncStorage.getItem(STORAGE_KEY),
        ]);

        const nextIncidentId = activeIncident?.incident_id ?? null;
        setIncidentId(nextIncidentId);

        if (!storedRaw) {
          return;
        }

        const stored = JSON.parse(storedRaw) as StoredThirdPartyDraft;
        if (!stored?.draft) {
          return;
        }

        if (stored.incidentId && nextIncidentId && stored.incidentId !== nextIncidentId) {
          return;
        }

        const storedParties = stored.draft.parties?.length
          ? stored.draft.parties
          : [{ ...EMPTY_PARTY }];

        setDraft({
          completionState: stored.draft.completionState ?? 'completed',
          parties: storedParties.map((party) => ({ ...EMPTY_PARTY, ...party })),
        });
      } catch {
        // Non-blocking.
      } finally {
        setIsInitializing(false);
      }
    };

    void initializeDraft();
  }, []);

  const nonEmptyPartyCount = useMemo(
    () => draft.parties.filter((party) => hasPartyData(party)).length,
    [draft.parties],
  );

  const updatePartyField = useCallback(
    (index: number, key: keyof ThirdPartyDraftItem, value: string) => {
      setDraft((previous) => {
        const parties = previous.parties.map((party, partyIndex) =>
          partyIndex === index
            ? {
                ...party,
                [key]: value,
              }
            : party,
        );

        return {
          ...previous,
          completionState: 'completed',
          parties,
        };
      });
    },
    [],
  );

  const addParty = useCallback(() => {
    setDraft((previous) => ({
      ...previous,
      completionState: 'completed',
      parties: [...previous.parties, { ...EMPTY_PARTY }],
    }));
  }, []);

  const removeParty = useCallback((index: number) => {
    setDraft((previous) => {
      if (previous.parties.length === 1) {
        return {
          ...previous,
          parties: [{ ...EMPTY_PARTY }],
        };
      }

      return {
        ...previous,
        parties: previous.parties.filter((_, partyIndex) => partyIndex !== index),
      };
    });
  }, []);

  const markFieldUnknown = useCallback((index: number, key: keyof ThirdPartyDraftItem) => {
    updatePartyField(index, key, UNKNOWN_TOKEN);
  }, [updatePartyField]);

  const handleSaveAndContinue = useCallback(async () => {
    setErrorText(null);
    setIsSaving(true);

    try {
      const nextDraft: ThirdPartyDraft = {
        ...draft,
        completionState: 'completed',
      };
      await persistDraft(nextDraft, incidentId);
      setDraft(nextDraft);
      emitProtocolAnalyticsEvent('party_info_saved', {
        incidentId,
        workflowCorrelationId: protocolContext.workflowCorrelationId,
        payload: {
          completion_state: nextDraft.completionState,
          entered_party_count: nonEmptyPartyCount,
        },
      });
      completeRoute('ThirdPartyInfo');
      navigation.navigate('MediaCapture', { destinationPromptType: 'general_scene' });
    } finally {
      setIsSaving(false);
    }
  }, [
    completeRoute,
    draft,
    incidentId,
    navigation,
    nonEmptyPartyCount,
    persistDraft,
    protocolContext.workflowCorrelationId,
  ]);

  const handleSkip = useCallback(async () => {
    setErrorText(null);
    setIsSaving(true);

    try {
      const nextDraft: ThirdPartyDraft = {
        ...draft,
        completionState: 'skipped',
      };

      await persistDraft(nextDraft, incidentId);
      setDraft(nextDraft);
      emitProtocolAnalyticsEvent('party_info_saved', {
        incidentId,
        workflowCorrelationId: protocolContext.workflowCorrelationId,
        payload: {
          completion_state: nextDraft.completionState,
          entered_party_count: nonEmptyPartyCount,
        },
      });
      completeRoute('ThirdPartyInfo');
      navigation.navigate('MediaCapture', { destinationPromptType: 'general_scene' });
    } finally {
      setIsSaving(false);
    }
  }, [
    completeRoute,
    draft,
    incidentId,
    navigation,
    nonEmptyPartyCount,
    persistDraft,
    protocolContext.workflowCorrelationId,
  ]);

  const handleTakePhotoInstead = useCallback(
    async (promptType: MediaPromptType) => {
      setErrorText(null);
      setIsSaving(true);
      try {
        const nextDraft: ThirdPartyDraft = {
          ...draft,
          completionState: draft.completionState,
        };
        await persistDraft(nextDraft, incidentId);
        emitProtocolAnalyticsEvent('party_info_saved', {
          incidentId,
          workflowCorrelationId: protocolContext.workflowCorrelationId,
          payload: {
            completion_state: nextDraft.completionState,
            entered_party_count: nonEmptyPartyCount,
            transitioned_to_media_prompt: promptType,
          },
        });
        completeRoute('ThirdPartyInfo');
        navigation.navigate('MediaCapture', { destinationPromptType: promptType });
      } finally {
        setIsSaving(false);
      }
    },
    [
      completeRoute,
      draft,
      incidentId,
      navigation,
      nonEmptyPartyCount,
      persistDraft,
      protocolContext.workflowCorrelationId,
    ],
  );

  if (isInitializing) {
    return (
      <View style={styles.stateContainer}>
        <Text variant="bodyLarge">Loading third-party details…</Text>
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.headerBlock}>
        <Text variant="headlineSmall">Third Party Info</Text>
        <Text variant="bodyMedium" style={styles.description}>
          Add third-party information when available. Most fields are optional. If you do not know
          a value, tap “Mark unknown” or type “unknown”.
        </Text>
      </View>

      <View style={styles.guidanceBlock}>
        <Text variant="bodySmall" style={styles.guidanceText}>
          Parties with no entered fields are omitted from API sync.
        </Text>
        <Text variant="bodySmall" style={styles.guidanceText}>
          Current entered party count: {nonEmptyPartyCount}
        </Text>
      </View>

      {draft.parties.map((party, index) => (
        <View key={`party-${index}`} style={styles.partyCard}>
          <Text variant="titleMedium">Third party #{index + 1}</Text>

          <View style={styles.inputBlock}>
            <TextInput
              mode="outlined"
              label="Full name"
              value={party.fullName}
              onChangeText={(value) => updatePartyField(index, 'fullName', value)}
              placeholder="e.g., Alex Smith"
            />
            <Button
              mode="text"
              onPress={() => markFieldUnknown(index, 'fullName')}
              compact
            >
              Mark unknown
            </Button>
          </View>

          <View style={styles.inputBlock}>
            <TextInput
              mode="outlined"
              label="Phone number"
              value={party.phoneNumber}
              onChangeText={(value) => updatePartyField(index, 'phoneNumber', value)}
              placeholder="Optional"
            />
            <Button
              mode="text"
              onPress={() => markFieldUnknown(index, 'phoneNumber')}
              compact
            >
              Mark unknown
            </Button>
          </View>

          <TextInput
            mode="outlined"
            label="Vehicle description"
            value={party.vehicleDescription}
            onChangeText={(value) => updatePartyField(index, 'vehicleDescription', value)}
            placeholder="Color, make/model, plate details if available"
          />

          <TextInput
            mode="outlined"
            label="Insurer name"
            value={party.insurerName}
            onChangeText={(value) => updatePartyField(index, 'insurerName', value)}
            placeholder="Optional"
          />

          <TextInput
            mode="outlined"
            label="Policy number"
            value={party.policyNumber}
            onChangeText={(value) => updatePartyField(index, 'policyNumber', value)}
            placeholder="Optional"
          />

          <TextInput
            mode="outlined"
            label="Notes"
            value={party.notes}
            onChangeText={(value) => updatePartyField(index, 'notes', value)}
            multiline
            numberOfLines={3}
            placeholder="Optional notes"
          />

          <View style={styles.inlineActions}>
            <Button
              mode="outlined"
              onPress={() => void handleTakePhotoInstead('third_party_vehicle')}
              disabled={isSaving}
            >
              Take Photo Instead (Vehicle)
            </Button>
            <Button
              mode="outlined"
              onPress={() => void handleTakePhotoInstead('third_party_document')}
              disabled={isSaving}
            >
              Take Photo Instead (Document)
            </Button>
          </View>

          <Button mode="text" onPress={() => removeParty(index)} disabled={isSaving}>
            Remove party
          </Button>
        </View>
      ))}

      <Button mode="outlined" onPress={addParty} disabled={isSaving}>
        Add another party
      </Button>

      {errorText ? <HelperText type="error">{errorText}</HelperText> : null}

      <View style={styles.actions}>
        <Button mode="outlined" onPress={() => navigation.goBack()} disabled={isSaving}>
          Back
        </Button>
        <Button mode="outlined" onPress={() => void handleSkip()} loading={isSaving}>
          Skip for now
        </Button>
        <Button mode="contained" onPress={() => void handleSaveAndContinue()} loading={isSaving}>
          Third-party info saved
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
    gap: 8,
  },
  description: {
    color: '#5f6b7a',
  },
  guidanceBlock: {
    gap: 2,
  },
  guidanceText: {
    color: '#334155',
  },
  partyCard: {
    borderWidth: 1,
    borderColor: '#dbe2ea',
    borderRadius: 10,
    padding: 14,
    gap: 10,
  },
  inputBlock: {
    gap: 2,
  },
  inlineActions: {
    gap: 8,
  },
  actions: {
    marginTop: 'auto',
    gap: 12,
  },
});

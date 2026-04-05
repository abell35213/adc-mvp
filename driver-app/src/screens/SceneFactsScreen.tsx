import { useCallback, useEffect, useMemo, useState } from 'react';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Button, HelperText, Text, TextInput } from 'react-native-paper';
import * as SecureStore from 'expo-secure-store';

import {
  DriverSceneFactsPayload,
  getDriverActiveIncident,
  patchDriverIncidentSceneFacts,
} from '../api';
import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import { emitTimelineAndAnalyticsEvent } from '../telemetry/protocolEvents';

type Props = NativeStackScreenProps<RootStackParamList, 'SceneFacts'>;

type SceneFactsDraft = {
  incidentDateTime: string;
  locationText: string;
  locationLatitude: string;
  locationLongitude: string;
  injuriesReported: boolean | null;
  policeCalled: boolean | null;
  vehicleDrivable: boolean | null;
  shortDescription: string;
};

type StoredSceneFactsDraft = {
  incidentId: string | null;
  draft: SceneFactsDraft;
};

const STORAGE_KEY = 'driver_scene_facts_draft_v1';
const TOTAL_STEPS = 3;

const EMPTY_DRAFT: SceneFactsDraft = {
  incidentDateTime: '',
  locationText: '',
  locationLatitude: '',
  locationLongitude: '',
  injuriesReported: null,
  policeCalled: null,
  vehicleDrivable: null,
  shortDescription: '',
};

function asNullableNumber(value: string): number | null {
  if (!value.trim()) {
    return null;
  }

  const parsed = Number(value.trim());
  return Number.isFinite(parsed) ? parsed : null;
}

function buildSceneFactsPayload(draft: SceneFactsDraft): DriverSceneFactsPayload {
  const locationText = draft.locationText.trim();
  const latitude = asNullableNumber(draft.locationLatitude);
  const longitude = asNullableNumber(draft.locationLongitude);

  return {
    incident_datetime_utc: draft.incidentDateTime.trim(),
    location_text: locationText || null,
    location_gps:
      latitude != null && longitude != null
        ? {
            latitude,
            longitude,
          }
        : null,
    injuries_reported: Boolean(draft.injuriesReported),
    police_called: Boolean(draft.policeCalled),
    vehicle_drivable: Boolean(draft.vehicleDrivable),
    short_description: draft.shortDescription.trim(),
  };
}

function validateStep(stepIndex: number, draft: SceneFactsDraft): string | null {
  if (stepIndex === 0) {
    if (!draft.incidentDateTime.trim()) {
      return 'Incident date/time is required.';
    }

    const hasLocationText = Boolean(draft.locationText.trim());
    const hasGps =
      asNullableNumber(draft.locationLatitude) != null &&
      asNullableNumber(draft.locationLongitude) != null;

    if (!hasLocationText && !hasGps) {
      return 'Provide location text or both GPS coordinates.';
    }
  }

  if (stepIndex === 1) {
    if (
      draft.injuriesReported == null ||
      draft.policeCalled == null ||
      draft.vehicleDrivable == null
    ) {
      return 'Please answer all yes/no scene safety questions.';
    }
  }

  if (stepIndex === 2 && !draft.shortDescription.trim()) {
    return 'Short description is required.';
  }

  return null;
}

function YesNoQuestion({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean | null;
  onChange: (next: boolean) => void;
}) {
  return (
    <View style={styles.questionBlock}>
      <Text variant="titleMedium">{label}</Text>
      <View style={styles.yesNoRow}>
        <Button mode={value === true ? 'contained' : 'outlined'} onPress={() => onChange(true)}>
          Yes
        </Button>
        <Button mode={value === false ? 'contained' : 'outlined'} onPress={() => onChange(false)}>
          No
        </Button>
      </View>
    </View>
  );
}

export default function SceneFactsScreen({ navigation }: Props) {
  const { completeRoute } = useProtocolFlow();
  useProtocolRouteGuard('SceneFacts', navigation);

  const [stepIndex, setStepIndex] = useState(0);
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [draft, setDraft] = useState<SceneFactsDraft>(EMPTY_DRAFT);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  const persistDraft = useCallback(
    async (nextDraft: SceneFactsDraft, currentIncidentId: string | null) => {
      const payload: StoredSceneFactsDraft = {
        incidentId: currentIncidentId,
        draft: nextDraft,
      };

      await SecureStore.setItemAsync(STORAGE_KEY, JSON.stringify(payload));

      const trimmedIncidentId = currentIncidentId?.trim();
      if (trimmedIncidentId) {
        try {
          await patchDriverIncidentSceneFacts(trimmedIncidentId, buildSceneFactsPayload(nextDraft));
        } catch {
          // Offline or server unavailable; local draft remains source of truth.
        }
      }

      emitTimelineAndAnalyticsEvent('driver_scene_facts_saved');
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

        const stored = JSON.parse(storedRaw) as StoredSceneFactsDraft;
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
        // Non-blocking; allow user to proceed with empty draft.
      } finally {
        setIsInitializing(false);
      }
    };

    void initializeDraft();
  }, []);

  const stepError = useMemo(() => validateStep(stepIndex, draft), [draft, stepIndex]);

  const handleStepChange = useCallback(
    async (nextStepIndex: number) => {
      setErrorText(null);

      const validationError = validateStep(stepIndex, draft);
      if (validationError) {
        setErrorText(validationError);
        return;
      }

      setIsSaving(true);
      try {
        await persistDraft(draft, incidentId);
        setStepIndex(nextStepIndex);
      } finally {
        setIsSaving(false);
      }
    },
    [draft, incidentId, persistDraft, stepIndex],
  );

  const handleContinue = useCallback(async () => {
    if (stepIndex < TOTAL_STEPS - 1) {
      await handleStepChange(stepIndex + 1);
      return;
    }

    const validationError = validateStep(stepIndex, draft);
    if (validationError) {
      setErrorText(validationError);
      return;
    }

    setIsSaving(true);
    setErrorText(null);

    try {
      await persistDraft(draft, incidentId);
      completeRoute('SceneFacts');
      navigation.navigate('ThirdPartyInfo');
    } finally {
      setIsSaving(false);
    }
  }, [completeRoute, draft, handleStepChange, incidentId, navigation, persistDraft, stepIndex]);

  const handleBack = useCallback(async () => {
    if (stepIndex > 0) {
      await handleStepChange(stepIndex - 1);
      return;
    }

    navigation.goBack();
  }, [handleStepChange, navigation, stepIndex]);

  if (isInitializing) {
    return (
      <View style={styles.stateContainer}>
        <Text variant="bodyLarge">Loading scene facts…</Text>
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.headerBlock}>
        <Text variant="headlineSmall">Scene Facts</Text>
        <Text variant="bodyMedium" style={styles.description}>
          Step {stepIndex + 1} of {TOTAL_STEPS}
        </Text>
      </View>

      {stepIndex === 0 ? (
        <View style={styles.formBlock}>
          <TextInput
            mode="outlined"
            label="Incident date/time (UTC)"
            value={draft.incidentDateTime}
            onChangeText={(value) => setDraft((previous) => ({ ...previous, incidentDateTime: value }))}
            placeholder="2026-04-05T13:45:00Z"
          />
          <TextInput
            mode="outlined"
            label="Location text"
            value={draft.locationText}
            onChangeText={(value) => setDraft((previous) => ({ ...previous, locationText: value }))}
            placeholder="123 Main St, Springfield"
          />
          <Text variant="bodySmall" style={styles.helperText}>
            Provide either location text or both GPS coordinates.
          </Text>
          <View style={styles.gpsRow}>
            <TextInput
              style={styles.gpsField}
              mode="outlined"
              label="Latitude"
              value={draft.locationLatitude}
              onChangeText={(value) =>
                setDraft((previous) => ({ ...previous, locationLatitude: value }))
              }
              keyboardType="decimal-pad"
              placeholder="37.7749"
            />
            <TextInput
              style={styles.gpsField}
              mode="outlined"
              label="Longitude"
              value={draft.locationLongitude}
              onChangeText={(value) =>
                setDraft((previous) => ({ ...previous, locationLongitude: value }))
              }
              keyboardType="decimal-pad"
              placeholder="-122.4194"
            />
          </View>
        </View>
      ) : null}

      {stepIndex === 1 ? (
        <View style={styles.formBlock}>
          <YesNoQuestion
            label="Were injuries reported?"
            value={draft.injuriesReported}
            onChange={(value) => setDraft((previous) => ({ ...previous, injuriesReported: value }))}
          />
          <YesNoQuestion
            label="Were police called?"
            value={draft.policeCalled}
            onChange={(value) => setDraft((previous) => ({ ...previous, policeCalled: value }))}
          />
          <YesNoQuestion
            label="Is the vehicle drivable?"
            value={draft.vehicleDrivable}
            onChange={(value) => setDraft((previous) => ({ ...previous, vehicleDrivable: value }))}
          />
        </View>
      ) : null}

      {stepIndex === 2 ? (
        <View style={styles.formBlock}>
          <TextInput
            mode="outlined"
            label="Short description"
            value={draft.shortDescription}
            onChangeText={(value) => setDraft((previous) => ({ ...previous, shortDescription: value }))}
            multiline
            numberOfLines={5}
            placeholder="Briefly describe what happened."
          />
        </View>
      ) : null}

      {errorText ? <HelperText type="error">{errorText}</HelperText> : null}
      {!errorText && stepError ? <HelperText type="info">{stepError}</HelperText> : null}

      <View style={styles.actions}>
        <Button mode="outlined" onPress={() => void handleBack()} disabled={isSaving}>
          {stepIndex > 0 ? 'Previous step' : 'Back'}
        </Button>
        <Button mode="contained" onPress={() => void handleContinue()} loading={isSaving}>
          {stepIndex >= TOTAL_STEPS - 1 ? 'Facts recorded' : 'Next step'}
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
  formBlock: {
    gap: 12,
  },
  helperText: {
    color: '#5f6b7a',
  },
  gpsRow: {
    flexDirection: 'row',
    gap: 12,
  },
  gpsField: {
    flex: 1,
  },
  questionBlock: {
    gap: 8,
  },
  yesNoRow: {
    flexDirection: 'row',
    gap: 12,
  },
  actions: {
    marginTop: 'auto',
    gap: 12,
  },
});

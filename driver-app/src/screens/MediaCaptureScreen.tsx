import { useCallback, useEffect, useMemo, useState } from 'react';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Button, Chip, Divider, HelperText, Surface, Text } from 'react-native-paper';
import * as SecureStore from 'expo-secure-store';

import { getDriverActiveIncident } from '../api';
import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';

type Props = NativeStackScreenProps<RootStackParamList, 'MediaCapture'>;

type MediaPromptType =
  | 'truck_damage'
  | 'other_vehicle'
  | 'license_plate'
  | 'wide_scene'
  | 'road_signal_context';

type MediaPromptStatus = 'pending' | 'captured' | 'skipped';
type CaptureSource = 'camera' | 'library';

type PromptState = {
  type: MediaPromptType;
  title: string;
  helperText: string;
  status: MediaPromptStatus;
};

type CapturedArtifact = {
  id: string;
  promptType: MediaPromptType;
  source: CaptureSource;
  capturedAtUtc: string;
  gps: {
    latitude: number;
    longitude: number;
  } | null;
};

type StoredMediaCaptureDraft = {
  incidentId: string | null;
  prompts: Array<{
    type: MediaPromptType;
    status: MediaPromptStatus;
  }>;
  queue: CapturedArtifact[];
};

const STORAGE_KEY = 'driver_media_capture_draft_v1';

const PROMPT_CONFIG: Array<Omit<PromptState, 'status'>> = [
  {
    type: 'truck_damage',
    title: 'Truck damage',
    helperText: 'Capture close and medium shots of your truck damage.',
  },
  {
    type: 'other_vehicle',
    title: 'Other vehicle',
    helperText: 'Capture the other vehicle damage and identifying details.',
  },
  {
    type: 'license_plate',
    title: 'License plate',
    helperText: 'Capture plate details clearly and head-on if possible.',
  },
  {
    type: 'wide_scene',
    title: 'Wide scene',
    helperText: 'Capture a wide angle that shows all vehicles and lane positions.',
  },
  {
    type: 'road_signal_context',
    title: 'Road/signal context',
    helperText: 'Capture nearby signs, lights, lane markings, and intersections.',
  },
];

const INITIAL_PROMPTS: PromptState[] = PROMPT_CONFIG.map((prompt) => ({
  ...prompt,
  status: 'pending',
}));

async function getOptionalGps(): Promise<{ latitude: number; longitude: number } | null> {
  const geolocationApi = globalThis?.navigator?.geolocation;
  if (!geolocationApi) {
    return null;
  }

  return new Promise((resolve) => {
    geolocationApi.getCurrentPosition(
      (position) => {
        resolve({
          latitude: position.coords.latitude,
          longitude: position.coords.longitude,
        });
      },
      () => resolve(null),
      {
        enableHighAccuracy: false,
        timeout: 2500,
      },
    );
  });
}

function mergePromptStatuses(
  existing: PromptState[],
  stored: StoredMediaCaptureDraft | null,
): PromptState[] {
  if (!stored) {
    return existing;
  }

  return existing.map((prompt) => {
    const storedPrompt = stored.prompts.find((candidate) => candidate.type === prompt.type);
    return {
      ...prompt,
      status: storedPrompt?.status ?? 'pending',
    };
  });
}

export default function MediaCaptureScreen({ navigation }: Props) {
  const { completeRoute } = useProtocolFlow();
  useProtocolRouteGuard('MediaCapture', navigation);

  const [incidentId, setIncidentId] = useState<string | null>(null);
  const [prompts, setPrompts] = useState<PromptState[]>(INITIAL_PROMPTS);
  const [queue, setQueue] = useState<CapturedArtifact[]>([]);
  const [isInitializing, setIsInitializing] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorText, setErrorText] = useState<string | null>(null);

  const pendingPrompts = useMemo(
    () => prompts.filter((prompt) => prompt.status === 'pending').length,
    [prompts],
  );

  const persistDraft = useCallback(
    async (nextPrompts: PromptState[], nextQueue: CapturedArtifact[], nextIncidentId: string | null) => {
      const payload: StoredMediaCaptureDraft = {
        incidentId: nextIncidentId,
        prompts: nextPrompts.map((prompt) => ({
          type: prompt.type,
          status: prompt.status,
        })),
        queue: nextQueue,
      };

      await SecureStore.setItemAsync(STORAGE_KEY, JSON.stringify(payload));
    },
    [],
  );

  useEffect(() => {
    const initialize = async () => {
      let nextIncidentId: string | null = null;
      let storedRaw: string | null = null;

      const [activeIncidentResult, storedDraftResult] = await Promise.allSettled([
        getDriverActiveIncident(),
        SecureStore.getItemAsync(STORAGE_KEY),
      ]);

      if (activeIncidentResult.status === 'fulfilled') {
        nextIncidentId = activeIncidentResult.value?.incident_id ?? null;
        setIncidentId(nextIncidentId);
      }

      if (storedDraftResult.status === 'fulfilled') {
        storedRaw = storedDraftResult.value;
      }

      try {
        if (!storedRaw) {
          return;
        }

        const stored = JSON.parse(storedRaw) as StoredMediaCaptureDraft;

        if (stored.incidentId && nextIncidentId && stored.incidentId !== nextIncidentId) {
          return;
        }

        setPrompts((current) => mergePromptStatuses(current, stored));
        setQueue(Array.isArray(stored.queue) ? stored.queue : []);
      } catch {
        // Non-blocking initialization fallback.
      } finally {
        setIsInitializing(false);
      }
    };

    void initialize();
  }, []);

  const updatePromptStatus = useCallback(
    async (promptType: MediaPromptType, status: MediaPromptStatus, source?: CaptureSource) => {
      setIsSaving(true);
      setErrorText(null);

      try {
        const gps = source ? await getOptionalGps() : null;
        const nextQueue =
          source == null
            ? queue
            : [
                ...queue,
                {
                  id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
                  promptType,
                  source,
                  capturedAtUtc: new Date().toISOString(),
                  gps,
                },
              ];

        const nextPrompts = prompts.map((prompt) =>
          prompt.type === promptType
            ? {
                ...prompt,
                status,
              }
            : prompt,
        );

        await persistDraft(nextPrompts, nextQueue, incidentId);
        setPrompts(nextPrompts);
        setQueue(nextQueue);
      } catch {
        setErrorText('Unable to save media draft locally. Please retry.');
      } finally {
        setIsSaving(false);
      }
    },
    [incidentId, persistDraft, prompts, queue],
  );

  const handleContinue = useCallback(async () => {
    if (pendingPrompts > 0) {
      setErrorText('Resolve every media prompt (capture or skip) before continuing.');
      return;
    }

    completeRoute('MediaCapture');
    navigation.navigate('Narrative');
  }, [completeRoute, navigation, pendingPrompts]);

  if (isInitializing) {
    return (
      <View style={styles.stateContainer}>
        <Text variant="bodyLarge">Loading media capture prompts…</Text>
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.headerBlock}>
        <Text variant="headlineSmall">Media Capture</Text>
        <Text variant="bodyMedium" style={styles.description}>
          Capture the minimum required evidence set. Each prompt supports Take Photo, Upload Existing,
          or Skip.
        </Text>
      </View>

      <Surface style={styles.summaryCard} elevation={1}>
        <Text variant="titleMedium">Capture progress</Text>
        <Text variant="bodyMedium">Remaining prompts: {pendingPrompts}</Text>
        <Text variant="bodyMedium">Local queue items: {queue.length}</Text>
      </Surface>

      <View style={styles.promptList}>
        {prompts.map((prompt) => (
          <Surface key={prompt.type} style={styles.promptCard} elevation={1}>
            <View style={styles.promptHeader}>
              <Text variant="titleMedium">{prompt.title}</Text>
              <Chip compact mode="flat" selected>
                {prompt.status}
              </Chip>
            </View>
            <Text variant="bodySmall" style={styles.promptHelper}>
              {prompt.helperText}
            </Text>
            <View style={styles.buttonRow}>
              <Button
                mode="contained"
                compact
                onPress={() => updatePromptStatus(prompt.type, 'captured', 'camera')}
                loading={isSaving}
                disabled={isSaving}
              >
                Take Photo
              </Button>
              <Button
                mode="outlined"
                compact
                onPress={() => updatePromptStatus(prompt.type, 'captured', 'library')}
                loading={isSaving}
                disabled={isSaving}
              >
                Upload Existing
              </Button>
              <Button
                mode="text"
                compact
                onPress={() => updatePromptStatus(prompt.type, 'skipped')}
                loading={isSaving}
                disabled={isSaving}
              >
                Skip
              </Button>
            </View>
          </Surface>
        ))}
      </View>

      <HelperText type="error" visible={Boolean(errorText)}>
        {errorText}
      </HelperText>

      <Divider style={styles.divider} />

      <View style={styles.footerRow}>
        <Button mode="outlined" onPress={() => navigation.goBack()} disabled={isSaving}>
          Back
        </Button>
        <Button mode="contained" onPress={handleContinue} disabled={isSaving || pendingPrompts > 0}>
          Continue to Narrative
        </Button>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 20,
    gap: 14,
  },
  stateContainer: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
  },
  headerBlock: {
    gap: 8,
  },
  description: {
    color: '#475569',
  },
  summaryCard: {
    borderRadius: 10,
    padding: 14,
    gap: 4,
  },
  promptList: {
    gap: 12,
  },
  promptCard: {
    borderRadius: 10,
    padding: 14,
    gap: 10,
  },
  promptHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  promptHelper: {
    color: '#64748b',
  },
  buttonRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  divider: {
    marginTop: 6,
  },
  footerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
  },
});

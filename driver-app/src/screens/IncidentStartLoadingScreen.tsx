import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Platform, StyleSheet, View } from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ActivityIndicator, Button, HelperText, Surface, Text } from 'react-native-paper';

import {
  ApiRequestError,
  getDriverActiveIncident,
  initiateDriverIncident,
} from '../api';
import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';

type Props = NativeStackScreenProps<RootStackParamList, 'IncidentStartLoading'>;

const STARTUP_STAGES = [
  'starting protocol',
  'notifying safety',
  'initiating evidence capture',
  'preparing instructions',
] as const;

const INITIATE_TIMEOUT_MS = 12000;

export default function IncidentStartLoadingScreen({ navigation }: Props) {
  const { completeRoute, protocolContext, transitionWorkflow } = useProtocolFlow();
  useProtocolRouteGuard('IncidentStartLoading', navigation);

  const [activeStageIndex, setActiveStageIndex] = useState(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isRetrying, setIsRetrying] = useState(false);
  const isMountedRef = useRef(true);

  useEffect(
    () => () => {
      isMountedRef.current = false;
    },
    [],
  );

  const vehicleStrategyPayload = useMemo(() => {
    if (protocolContext.vehicleResolutionMethod === 'qr_scan') {
      return {
        vehicle_strategy: 'qr' as const,
        qr_token: protocolContext.qrToken ?? undefined,
      };
    }

    return {
      vehicle_strategy: 'last_assigned' as const,
      qr_token: undefined,
    };
  }, [protocolContext.qrToken, protocolContext.vehicleResolutionMethod]);

  const collectDeviceLocation = useCallback(async () => {
    if (!navigator?.geolocation) {
      return null;
    }

    return await new Promise<{
      latitude: number;
      longitude: number;
      accuracy_meters?: number | null;
      timestamp_utc?: string;
    } | null>((resolve) => {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          resolve({
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
            accuracy_meters: position.coords.accuracy ?? null,
            timestamp_utc: new Date(position.timestamp).toISOString(),
          });
        },
        () => resolve(null),
        { enableHighAccuracy: true, timeout: 4000, maximumAge: 30000 },
      );
    });
  }, []);

  const withTimeout = useCallback(
    async <T,>(work: Promise<T>, timeoutMs: number) => {
      const timeoutPromise = new Promise<T>((_, reject) => {
        setTimeout(() => reject(new Error('Request timed out.')), timeoutMs);
      });
      return await Promise.race([work, timeoutPromise]);
    },
    [],
  );

  const attemptAmbiguousRecovery = useCallback(async () => {
    try {
      return await getDriverActiveIncident();
    } catch {
      return null;
    }
  }, []);

  const isNetworkFailure = (error: unknown) =>
    error instanceof TypeError ||
    (error instanceof Error &&
      /network request failed|failed to fetch|network/i.test(error.message));

  const isDuplicateFailure = (error: unknown) =>
    error instanceof ApiRequestError &&
    (error.status === 409 ||
      /active incident|already exists|duplicate/i.test(error.message));

  const continueToInstructions = useCallback(() => {
    if (!isMountedRef.current) {
      return;
    }

    transitionWorkflow('incident_initiated');
    completeRoute('IncidentStartLoading');
    navigation.replace('InstructionStep');
  }, [completeRoute, navigation, transitionWorkflow]);

  const beginIncidentInitiation = useCallback(async () => {
    if (!isMountedRef.current) {
      return;
    }

    setErrorMessage(null);
    setIsRetrying(false);
    setActiveStageIndex(0);

    const device = {
      platform: Platform.OS,
      platform_version: Platform.Version,
      app: 'driver-app',
      captured_at: new Date().toISOString(),
    };

    try {
      const locationPromise = collectDeviceLocation();
      setActiveStageIndex(1);
      setActiveStageIndex(2);

      await withTimeout(
        initiateDriverIncident({
          ...vehicleStrategyPayload,
          device,
          device_location: await locationPromise,
        }),
        INITIATE_TIMEOUT_MS,
      );

      setActiveStageIndex(3);
      continueToInstructions();
    } catch (error) {
      const ambiguousFailure =
        isNetworkFailure(error) ||
        (error instanceof Error && /timed out/i.test(error.message));
      const duplicateFailure = isDuplicateFailure(error);

      if (duplicateFailure || ambiguousFailure) {
        const recoveredIncident = await attemptAmbiguousRecovery();
        if (recoveredIncident?.incident_id) {
          setActiveStageIndex(3);
          continueToInstructions();
          return;
        }
      }

      if (duplicateFailure) {
        setErrorMessage(
          'Another active incident already exists for this vehicle. Resume the active incident from home.',
        );
        return;
      }

      if (ambiguousFailure) {
        setErrorMessage(
          'Unable to confirm incident startup after timeout/network failure. Please retry.',
        );
        return;
      }

      setErrorMessage(
        error instanceof Error
          ? error.message
          : 'Unable to start incident protocol. Please retry.',
      );
    }
  }, [
    attemptAmbiguousRecovery,
    collectDeviceLocation,
    continueToInstructions,
    vehicleStrategyPayload,
    withTimeout,
  ]);

  useEffect(() => {
    void beginIncidentInitiation();
  }, [beginIncidentInitiation]);

  return (
    <View style={styles.container}>
      <Text variant="headlineMedium">Starting incident protocol</Text>
      <Text variant="bodyMedium" style={styles.description}>
        We are creating your incident and preparing instructions. Keep this screen open.
      </Text>

      <Surface style={styles.statusCard}>
        {STARTUP_STAGES.map((stage, index) => {
          const complete = index < activeStageIndex;
          const current = index === activeStageIndex;
          return (
            <View key={stage} style={styles.statusRow}>
              {complete ? (
                <Text style={styles.statusComplete}>✓</Text>
              ) : current ? (
                <ActivityIndicator size="small" />
              ) : (
                <Text style={styles.statusPending}>○</Text>
              )}
              <Text style={current ? styles.statusCurrentText : styles.statusText}>{stage}</Text>
            </View>
          );
        })}
      </Surface>

      {errorMessage ? (
        <View style={styles.errorContainer}>
          <HelperText type="error">{errorMessage}</HelperText>
          <View style={styles.actions}>
            <Button
              mode="contained"
              onPress={() => {
                setIsRetrying(true);
                void beginIncidentInitiation().finally(() => setIsRetrying(false));
              }}
              loading={isRetrying}
              disabled={isRetrying}
            >
              Retry startup
            </Button>
            <Button mode="outlined" onPress={() => navigation.navigate('DriverHome')}>
              Return home
            </Button>
          </View>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    padding: 24,
    gap: 16,
  },
  description: {
    color: '#5f6b7a',
  },
  statusCard: {
    borderRadius: 12,
    padding: 16,
    gap: 12,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  statusText: {
    textTransform: 'capitalize',
    color: '#5f6b7a',
  },
  statusCurrentText: {
    textTransform: 'capitalize',
    color: '#111827',
    fontWeight: '600',
  },
  statusComplete: {
    color: '#1f7a36',
    fontWeight: '700',
  },
  statusPending: {
    color: '#9aa5b1',
  },
  errorContainer: {
    gap: 12,
  },
  actions: {
    gap: 12,
  },
});

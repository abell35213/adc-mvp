import { useCallback, useMemo, useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Card, HelperText, Text } from 'react-native-paper';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';

import {
  DriverActiveIncidentResponse,
  DriverMeResponse,
  getDriverActiveIncident,
  getDriverMe,
} from '../api';
import { ProtocolRouteName, getFirstIncompleteRoute } from '../navigation/protocolFlow';
import { RootStackParamList } from '../navigation/types';
import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import {
  clearProtocolLocalDraftsAndResumeState,
  resolveProtocolResumeState,
} from '../store/protocolResumeStore';
import { emitProtocolAnalyticsEvent } from '../telemetry/protocolEvents';

type Props = NativeStackScreenProps<RootStackParamList, 'DriverHome'>;

export default function DriverHomeScreen({ navigation }: Props) {
  const [driver, setDriver] = useState<DriverMeResponse | null>(null);
  const [activeIncident, setActiveIncident] =
    useState<DriverActiveIncidentResponse | null>(null);
  const { restoreProtocol, resetProtocol, startProtocol } = useProtocolFlow();
  const [resumeCompletedRoutes, setResumeCompletedRoutes] = useState<Set<ProtocolRouteName>>(
    new Set(),
  );
  const [hasLocalDrafts, setHasLocalDrafts] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const loadHomeData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [driverResponse, activeIncidentResponse] = await Promise.all([
        getDriverMe(),
        getDriverActiveIncident(),
      ]);

      const activeIncidentId = activeIncidentResponse?.incident_id?.trim() || null;
      const resumeState = await resolveProtocolResumeState(activeIncidentId);

      setDriver(driverResponse);
      setActiveIncident(activeIncidentResponse);
      setResumeCompletedRoutes(resumeState.completedRoutes);
      setHasLocalDrafts(resumeState.hasLocalDrafts);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load home data.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadHomeData();
    }, [loadHomeData]),
  );

  const vehicleLabel = driver?.vehicle?.display_label ?? 'Unassigned';
  const canResumeIncident = activeIncident?.incident_id != null;

  const startNewIncidentProtocol = useCallback(() => {
    startProtocol();
    emitProtocolAnalyticsEvent('protocol_start_tapped');
    navigation.navigate('IncidentConfirm');
  }, [navigation, startProtocol]);

  const getNextActionRoute = useCallback((): ProtocolRouteName => {
    if (resumeCompletedRoutes.size > 0 || hasLocalDrafts) {
      return getFirstIncompleteRoute(resumeCompletedRoutes);
    }

    return 'IncidentStatus';
  }, [hasLocalDrafts, resumeCompletedRoutes]);

  const resumeSavedProtocol = useCallback(() => {
    const nextRoute = getNextActionRoute();
    emitProtocolAnalyticsEvent('protocol_resumed', {
      incidentId: activeIncident?.incident_id ?? null,
      payload: {
        resume_route: nextRoute,
      },
    });
    restoreProtocol(resumeCompletedRoutes);
    navigation.navigate(nextRoute);
  }, [
    activeIncident?.incident_id,
    getNextActionRoute,
    navigation,
    restoreProtocol,
    resumeCompletedRoutes,
  ]);

  const discardSavedProtocol = useCallback(async () => {
    await clearProtocolLocalDraftsAndResumeState();
    resetProtocol();
    setResumeCompletedRoutes(new Set());
    setHasLocalDrafts(false);
  }, [resetProtocol]);

  const hasResumableState = useMemo(
    () => canResumeIncident || hasLocalDrafts || resumeCompletedRoutes.size > 0,
    [canResumeIncident, hasLocalDrafts, resumeCompletedRoutes.size],
  );

  const handleStartIncidentProtocol = () => {
    if (!hasResumableState) {
      startNewIncidentProtocol();
      return;
    }

    Alert.alert(
      'Resume previous protocol?',
      'We found an in-progress incident and/or local draft data. Resume where you left off or discard local draft data and start a new protocol.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Resume',
          onPress: resumeSavedProtocol,
        },
        {
          text: 'Discard and start new',
          style: 'destructive',
          onPress: () => {
            void discardSavedProtocol().then(() => startNewIncidentProtocol());
          },
        },
      ],
    );
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <Text variant="headlineMedium">Driver Home</Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          {driver?.display_name ?? 'Driver'} • {driver?.phone_e164 ?? ''}
        </Text>
      </View>
      <Card style={styles.card}>
        <Card.Title title="Current vehicle" />
        <Card.Content>
          <Text variant="titleLarge">{vehicleLabel}</Text>
        </Card.Content>
      </Card>
      {error ? <HelperText type="error">{error}</HelperText> : null}
      <Button
        mode="contained"
        onPress={handleStartIncidentProtocol}
        loading={isLoading}
        disabled={isLoading}
        style={styles.button}
      >
        Start Incident Protocol
      </Button>
      <Button
        mode="outlined"
        onPress={() => navigation.navigate('QrScan')}
        style={styles.button}
      >
        Scan Vehicle QR
      </Button>
      {canResumeIncident ? (
        <Card style={styles.card}>
          <Card.Title title="Resume Incident" />
          <Card.Content style={styles.resumeContent}>
            <Text variant="bodyMedium">
              Incident #{activeIncident?.incident_id} is currently {activeIncident?.status}.
            </Text>
            <Button
              mode="contained-tonal"
              style={styles.resumeButton}
              onPress={resumeSavedProtocol}
            >
              Resume Incident
            </Button>
          </Card.Content>
        </Card>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    padding: 24,
    gap: 16,
  },
  header: {
    gap: 4,
  },
  subtitle: {
    color: '#5f6b7a',
  },
  card: {
    marginTop: 8,
  },
  button: {
    marginTop: 8,
  },
  resumeContent: {
    gap: 12,
  },
  resumeButton: {
    alignSelf: 'flex-start',
  },
});

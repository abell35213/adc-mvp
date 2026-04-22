import { useCallback, useMemo, useState } from 'react';
import { Linking, ScrollView, StyleSheet, View } from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { Button, Card, Chip, HelperText, Text } from 'react-native-paper';

import {
  DriverIncidentStatusResponse,
  getDriverActiveIncident,
  getDriverIncidentStatus,
} from '../api';
import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';

type Props = NativeStackScreenProps<RootStackParamList, 'IncidentStatus'>;

const SAFETY_MANAGER_NUMBER = '+18005551212';

export default function IncidentStatusScreen({ navigation }: Props) {
  const { completeRoute, resetProtocol } = useProtocolFlow();
  useProtocolRouteGuard('IncidentStatus', navigation);

  const [incidentStatus, setIncidentStatus] = useState<DriverIncidentStatusResponse | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const loadIncidentStatus = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const activeIncident = await getDriverActiveIncident();
      if (!activeIncident?.incident_id) {
        setIncidentStatus(null);
        return;
      }

      const response = await getDriverIncidentStatus(activeIncident.incident_id);
      setIncidentStatus(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load incident status.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void loadIncidentStatus();
    }, [loadIncidentStatus]),
  );

  const pendingItems = useMemo(() => {
    if (!incidentStatus) {
      return ['Unable to determine incident status.'];
    }

    const items: string[] = [];
    if (!incidentStatus.safety_notified) {
      items.push('Notify safety manager.');
    }
    if (incidentStatus.capture_state !== 'complete') {
      items.push('Continue evidence upload and verification.');
    }
    if (incidentStatus.status !== 'closed') {
      items.push('Review incident details before final closure.');
    }

    return items.length > 0 ? items : ['No pending items.'];
  }, [incidentStatus]);

  const artifactSummary = useMemo(() => {
    if (!incidentStatus) {
      return { uploaded: 0, pending: 0, failed: 0 };
    }

    if (incidentStatus.capture_state === 'complete') {
      return { uploaded: 1, pending: 0, failed: 0 };
    }

    if (incidentStatus.capture_state === 'failed') {
      return { uploaded: 0, pending: 0, failed: 1 };
    }

    return { uploaded: 0, pending: 1, failed: 0 };
  }, [incidentStatus]);

  const callSafety = async () => {
    await Linking.openURL(`tel:${SAFETY_MANAGER_NUMBER}`);
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.header}>
        <Text variant="headlineMedium">Incident Status</Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          Review your incident progress and complete any remaining actions.
        </Text>
      </View>

      {error ? <HelperText type="error">{error}</HelperText> : null}

      <Card style={styles.card}>
        <Card.Title title="Incident Metadata" />
        <Card.Content style={styles.sectionContent}>
          <Text>Incident ID: {incidentStatus?.incident_id ?? 'Not available'}</Text>
          <Text>Status: {incidentStatus?.status ?? 'Unknown'}</Text>
          <Text>
            Last evidence update: {incidentStatus?.last_evidence_update_utc ?? 'Not available'}
          </Text>
        </Card.Content>
      </Card>

      <Card style={styles.card}>
        <Card.Title title="Safety & Evidence Status" />
        <Card.Content style={styles.sectionContent}>
          <View style={styles.chipRow}>
            <Chip selected={Boolean(incidentStatus?.safety_notified)}>
              Safety notified: {incidentStatus?.safety_notified ? 'Yes' : 'No'}
            </Chip>
            <Chip selected={incidentStatus?.capture_state === 'complete'}>
              Capture: {incidentStatus?.capture_state ?? 'unknown'}
            </Chip>
          </View>
        </Card.Content>
      </Card>

      <Card style={styles.card}>
        <Card.Title title="Artifact Upload Summary" />
        <Card.Content style={styles.sectionContent}>
          <Text>Uploaded: {artifactSummary.uploaded}</Text>
          <Text>Pending: {artifactSummary.pending}</Text>
          <Text>Failed: {artifactSummary.failed}</Text>
        </Card.Content>
      </Card>

      <Card style={styles.card}>
        <Card.Title title="Pending Items" />
        <Card.Content style={styles.sectionContent}>
          {pendingItems.map((item) => (
            <Text key={item}>• {item}</Text>
          ))}
        </Card.Content>
      </Card>

      <View style={styles.actions}>
        <Button mode="outlined" onPress={() => navigation.navigate('MediaCapture')}>
          Add More Photos
        </Button>
        <Button mode="outlined" onPress={() => navigation.navigate('SceneFacts')}>
          Update Details
        </Button>
        <Button mode="outlined" onPress={() => void callSafety()}>
          Call Safety
        </Button>
      </View>

      <Button
        mode="contained"
        onPress={() => {
          completeRoute('IncidentStatus');
          resetProtocol();
          navigation.reset({ index: 0, routes: [{ name: 'DriverHome' }] });
        }}
        loading={isLoading}
        disabled={isLoading}
      >
        Return to home
      </Button>
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
    marginTop: 4,
  },
  sectionContent: {
    gap: 8,
  },
  chipRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  actions: {
    gap: 12,
    marginTop: 8,
  },
});

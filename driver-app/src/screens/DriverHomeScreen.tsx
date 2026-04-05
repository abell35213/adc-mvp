import { useCallback, useState } from 'react';
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
import { RootStackParamList } from '../navigation/types';
import { useProtocolFlow } from '../navigation/ProtocolFlowContext';

type Props = NativeStackScreenProps<RootStackParamList, 'DriverHome'>;

export default function DriverHomeScreen({ navigation }: Props) {
  const [driver, setDriver] = useState<DriverMeResponse | null>(null);
  const [activeIncident, setActiveIncident] =
    useState<DriverActiveIncidentResponse | null>(null);
  const { startProtocol } = useProtocolFlow();
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
      setDriver(driverResponse);
      setActiveIncident(activeIncidentResponse);
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
  const startNewIncidentProtocol = () => {
    startProtocol();
    navigation.navigate('IncidentConfirm');
  };

  const handleStartIncidentProtocol = () => {
    if (!canResumeIncident) {
      startNewIncidentProtocol();
      return;
    }

    Alert.alert(
      'Active incident in progress',
      'You have an active incident. Resume it to avoid duplicate submissions, or continue to start a new incident protocol.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Resume incident',
          onPress: () => navigation.navigate('IncidentStatus'),
        },
        {
          text: 'Start new',
          style: 'destructive',
          onPress: startNewIncidentProtocol,
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
              onPress={() => navigation.navigate('IncidentStatus')}
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

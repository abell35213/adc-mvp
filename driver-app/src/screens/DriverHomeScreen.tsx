import { useCallback, useState } from 'react';
import { Alert, ScrollView, StyleSheet, View } from 'react-native';
import { Button, Card, HelperText, Text } from 'react-native-paper';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';

import { DriverMeResponse, getDriverMe } from '../api';
import { RootStackParamList } from '../navigation/types';

type Props = NativeStackScreenProps<RootStackParamList, 'DriverHome'>;

export default function DriverHomeScreen({ navigation }: Props) {
  const [driver, setDriver] = useState<DriverMeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const loadDriver = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await getDriverMe();
      setDriver(response);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load profile.');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      loadDriver();
    }, [loadDriver]),
  );

  const vehicleLabel = driver?.vehicle?.display_label ?? 'Unassigned';

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
        onPress={() => Alert.alert('Incident Protocol', 'Starting soon.')}
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
        Scan QR override
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
    marginTop: 8,
  },
  button: {
    marginTop: 8,
  },
});

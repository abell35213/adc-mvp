import { useCallback, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Button, HelperText, Surface, Text, TextInput } from 'react-native-paper';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';

import { ApiRequestError, DriverMeResponse, getDriverMe } from '../api';
import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import { resolveVehicleQr } from '../services/incidents';

type Props = NativeStackScreenProps<RootStackParamList, 'VehicleConfirm'>;

type QrResolutionStatus = 'idle' | 'invalid' | 'failed';

export default function VehicleConfirmScreen({ navigation }: Props) {
  const { completeRoute, protocolContext, resolveVehicle } = useProtocolFlow();
  useProtocolRouteGuard('VehicleConfirm', navigation);

  const [driver, setDriver] = useState<DriverMeResponse | null>(null);
  const [isLoadingDriver, setIsLoadingDriver] = useState(false);
  const [isResolvingQr, setIsResolvingQr] = useState(false);
  const [qrTokenInput, setQrTokenInput] = useState('');
  const [qrStatus, setQrStatus] = useState<QrResolutionStatus>('idle');
  const [qrMessage, setQrMessage] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const assignedVehicle = driver?.vehicle;

  useFocusEffect(
    useCallback(() => {
      setIsLoadingDriver(true);
      setLoadError(null);
      getDriverMe()
        .then((response) => setDriver(response))
        .catch((error) =>
          setLoadError(
            error instanceof Error ? error.message : 'Unable to load assigned vehicle.',
          ),
        )
        .finally(() => setIsLoadingDriver(false));
    }, []),
  );

  const isVehicleResolved = protocolContext.vehicleResolved;
  const resolutionSummary = useMemo(() => {
    if (!isVehicleResolved || !protocolContext.vehicleId) {
      return null;
    }

    if (protocolContext.vehicleResolutionMethod === 'assigned_vehicle') {
      return `Using assigned vehicle ${protocolContext.vehicleId}.`;
    }

    return `QR resolved vehicle ${protocolContext.vehicleId}.`;
  }, [isVehicleResolved, protocolContext.vehicleId, protocolContext.vehicleResolutionMethod]);

  const handleAcceptAssignedVehicle = () => {
    if (!assignedVehicle) {
      return;
    }

    resolveVehicle({
      vehicleId: assignedVehicle.adc_vehicle_id,
      method: 'assigned_vehicle',
      qrToken: null,
    });
    setQrStatus('idle');
    setQrMessage(null);
  };

  const handleResolveQr = async () => {
    const token = qrTokenInput.trim();
    if (!token) {
      setQrStatus('invalid');
      setQrMessage('Enter a QR token before resolving.');
      return;
    }

    setIsResolvingQr(true);
    setQrStatus('idle');
    setQrMessage(null);
    try {
      const response = await resolveVehicleQr(token);
      resolveVehicle({
        vehicleId: response.adc_vehicle_id,
        method: 'qr_scan',
        qrToken: token,
      });
      setQrStatus('idle');
      setQrMessage(`QR resolved ${response.display_label}.`);
    } catch (error) {
      const isInvalid = error instanceof ApiRequestError && error.status === 400;
      setQrStatus(isInvalid ? 'invalid' : 'failed');
      setQrMessage(
        error instanceof Error ? error.message : 'Unable to resolve vehicle QR token.',
      );
    } finally {
      setIsResolvingQr(false);
    }
  };

  const handleContinue = () => {
    if (!protocolContext.vehicleResolved) {
      return;
    }

    completeRoute('VehicleConfirm');
    navigation.navigate('SafetyGate');
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.content}>
        <Text variant="headlineMedium">Confirm Vehicle</Text>
        <Text variant="bodyLarge" style={styles.description}>
          Resolve your reporting vehicle using your assigned vehicle or by scanning a QR token.
        </Text>

        <Surface style={styles.section}>
          <Text variant="titleMedium">Assigned vehicle</Text>
          <Text style={styles.sectionDescription}>
            {assignedVehicle
              ? `${assignedVehicle.display_label} (${assignedVehicle.adc_vehicle_id})`
              : 'No assigned vehicle found for this driver.'}
          </Text>
          {loadError ? <HelperText type="error">{loadError}</HelperText> : null}
          <Button
            mode="contained-tonal"
            onPress={handleAcceptAssignedVehicle}
            disabled={!assignedVehicle || isLoadingDriver}
            loading={isLoadingDriver}
          >
            Accept assigned vehicle
          </Button>
        </Surface>

        <Surface style={styles.section}>
          <Text variant="titleMedium">QR scan (primary/fallback)</Text>
          <Text style={styles.sectionDescription}>
            Use this when no assigned vehicle is shown, or to override with the physical vehicle QR.
          </Text>
          <TextInput
            mode="outlined"
            label="QR token"
            value={qrTokenInput}
            onChangeText={(value) => {
              setQrTokenInput(value);
              if (qrStatus !== 'idle') {
                setQrStatus('idle');
                setQrMessage(null);
              }
            }}
            autoCapitalize="none"
            autoCorrect={false}
          />
          {qrMessage ? (
            <HelperText type={qrStatus === 'failed' || qrStatus === 'invalid' ? 'error' : 'info'}>
              {qrMessage}
            </HelperText>
          ) : null}
          {qrStatus === 'invalid' ? (
            <Button
              mode="text"
              onPress={() => {
                setQrStatus('idle');
                setQrMessage(null);
                setQrTokenInput('');
              }}
            >
              Retry QR resolution
            </Button>
          ) : null}
          <Button mode="contained" onPress={handleResolveQr} loading={isResolvingQr}>
            Resolve QR vehicle
          </Button>
        </Surface>

        {resolutionSummary ? <Text style={styles.successText}>{resolutionSummary}</Text> : null}
      </View>

      <View style={styles.actions}>
        <Button mode="outlined" onPress={() => navigation.goBack()}>
          Back
        </Button>
        <Button mode="contained" onPress={handleContinue} disabled={!isVehicleResolved}>
          Vehicle confirmed
        </Button>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    justifyContent: 'space-between',
    padding: 24,
    gap: 24,
  },
  content: {
    gap: 16,
  },
  description: {
    color: '#5f6b7a',
  },
  section: {
    borderRadius: 12,
    padding: 16,
    gap: 8,
  },
  sectionDescription: {
    color: '#5f6b7a',
  },
  successText: {
    color: '#1f7a36',
  },
  actions: {
    gap: 12,
  },
});

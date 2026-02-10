import { useCallback, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useFocusEffect } from '@react-navigation/native';
import { CameraView, useCameraPermissions } from 'expo-camera';

import { resolveQr } from '../api';
import { RootStackParamList } from '../navigation/types';

type Props = NativeStackScreenProps<RootStackParamList, 'QrScan'>;

const QR_PREFIX = 'adc://vehicle/';

export default function QrScanScreen({ navigation }: Props) {
  const [permission, requestPermission] = useCameraPermissions();
  const [isScanning, setIsScanning] = useState(true);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      setIsScanning(true);
      setStatusMessage(null);
    }, []),
  );

  const handleBarcodeScanned = async ({ data }: { data: string }) => {
    if (!isScanning) {
      return;
    }

    setIsScanning(false);
    if (!data.startsWith(QR_PREFIX)) {
      setStatusMessage('Invalid QR code. Please scan an ADC vehicle code.');
      return;
    }

    const qrToken = data.slice(QR_PREFIX.length).trim();
    if (!qrToken) {
      setStatusMessage('QR code is missing a vehicle token.');
      return;
    }

    try {
      const response = await resolveQr(qrToken);
      setStatusMessage(`Resolved vehicle ${response.display_label}.`);
      setTimeout(() => navigation.goBack(), 900);
    } catch (err) {
      setStatusMessage(
        err instanceof Error ? err.message : 'Failed to resolve vehicle.',
      );
    }
  };

  if (!permission) {
    return (
      <View style={styles.centered}>
        <Text>Requesting camera access…</Text>
      </View>
    );
  }

  if (!permission.granted) {
    return (
      <View style={styles.centered}>
        <Text variant="titleMedium">Camera access is required.</Text>
        <Button mode="contained" onPress={requestPermission} style={styles.button}>
          Allow camera
        </Button>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView
        style={styles.camera}
        onBarcodeScanned={handleBarcodeScanned}
        barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
      />
      <View style={styles.overlay}>
        <Text variant="titleMedium" style={styles.overlayText}>
          Scan an ADC vehicle QR code
        </Text>
        {statusMessage ? (
          <>
            <Text style={styles.status}>{statusMessage}</Text>
            <Button
              mode="outlined"
              onPress={() => {
                setStatusMessage(null);
                setIsScanning(true);
              }}
            >
              Scan again
            </Button>
          </>
        ) : null}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  camera: {
    flex: 1,
  },
  overlay: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    padding: 24,
    gap: 8,
    backgroundColor: 'rgba(0,0,0,0.6)',
  },
  overlayText: {
    color: '#ffffff',
  },
  status: {
    color: '#ffffff',
  },
  centered: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
    gap: 12,
  },
  button: {
    marginTop: 8,
  },
});

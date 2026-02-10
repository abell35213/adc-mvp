import { useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet, View } from 'react-native';
import { Button, HelperText, Text, TextInput } from 'react-native-paper';
import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { verifyOtp } from '../api';
import { setStoredToken } from '../auth';
import { RootStackParamList } from '../navigation/types';

type Props = NativeStackScreenProps<RootStackParamList, 'OtpEntry'>;

export default function OtpEntryScreen({ navigation, route }: Props) {
  const { phoneE164 } = route.params;
  const [otpCode, setOtpCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleVerify = async () => {
    if (!otpCode.trim()) {
      setError('Enter the code we sent you.');
      return;
    }

    setError(null);
    setIsLoading(true);
    try {
      const response = await verifyOtp(phoneE164, otpCode.trim());
      const token = response.token ?? response.access_token ?? response.jwt;
      if (!token) {
        throw new Error('OTP verified but no token returned.');
      }
      await setStoredToken(token);
      navigation.reset({ index: 0, routes: [{ name: 'DriverHome' }] });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to verify OTP.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.select({ ios: 'padding', android: undefined })}
    >
      <View style={styles.content}>
        <Text variant="headlineMedium">Enter OTP</Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          We sent a code to {phoneE164}.
        </Text>
        <TextInput
          label="One-time code"
          value={otpCode}
          onChangeText={setOtpCode}
          keyboardType="number-pad"
          style={styles.input}
        />
        {error ? <HelperText type="error">{error}</HelperText> : null}
        <Button
          mode="contained"
          onPress={handleVerify}
          loading={isLoading}
          disabled={isLoading}
          style={styles.button}
        >
          Verify & Continue
        </Button>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  content: {
    flex: 1,
    justifyContent: 'center',
    padding: 24,
    gap: 12,
  },
  subtitle: {
    color: '#5f6b7a',
  },
  input: {
    marginTop: 16,
  },
  button: {
    marginTop: 12,
  },
});

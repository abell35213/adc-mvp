import { useState } from 'react';
import { KeyboardAvoidingView, Platform, StyleSheet, View } from 'react-native';
import { Button, HelperText, Text, TextInput } from 'react-native-paper';
import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { requestOtp } from '../api';
import { RootStackParamList } from '../navigation/types';

type Props = NativeStackScreenProps<RootStackParamList, 'PhoneEntry'>;

export default function PhoneEntryScreen({ navigation }: Props) {
  const [phoneE164, setPhoneE164] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleRequestOtp = async () => {
    if (!phoneE164.trim()) {
      setError('Enter your phone number.');
      return;
    }

    setError(null);
    setIsLoading(true);
    try {
      await requestOtp(phoneE164.trim());
      navigation.navigate('OtpEntry', { phoneE164: phoneE164.trim() });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to request OTP.');
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
        <Text variant="headlineMedium">Driver Sign In</Text>
        <Text variant="bodyMedium" style={styles.subtitle}>
          Enter your phone number to receive a one-time code.
        </Text>
        <TextInput
          label="Phone number"
          value={phoneE164}
          onChangeText={setPhoneE164}
          keyboardType="phone-pad"
          autoComplete="tel"
          style={styles.input}
        />
        {error ? <HelperText type="error">{error}</HelperText> : null}
        <Button
          mode="contained"
          onPress={handleRequestOtp}
          loading={isLoading}
          disabled={isLoading}
          style={styles.button}
        >
          Send OTP
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

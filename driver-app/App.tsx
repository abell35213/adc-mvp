import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ActivityIndicator, PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { getStoredToken } from './src/auth';
import { RootStackParamList } from './src/navigation/types';
import DriverHomeScreen from './src/screens/DriverHomeScreen';
import OtpEntryScreen from './src/screens/OtpEntryScreen';
import PhoneEntryScreen from './src/screens/PhoneEntryScreen';
import QrScanScreen from './src/screens/QrScanScreen';

const Stack = createNativeStackNavigator<RootStackParamList>();

export default function App() {
  const [initialRoute, setInitialRoute] =
    useState<keyof RootStackParamList | null>(null);

  useEffect(() => {
    getStoredToken()
      .then((token) => setInitialRoute(token ? 'DriverHome' : 'PhoneEntry'))
      .catch(() => setInitialRoute('PhoneEntry'));
  }, []);

  if (!initialRoute) {
    return (
      <PaperProvider>
        <SafeAreaProvider>
          <View style={styles.loading}>
            <ActivityIndicator animating />
          </View>
        </SafeAreaProvider>
      </PaperProvider>
    );
  }

  return (
    <PaperProvider>
      <SafeAreaProvider>
        <NavigationContainer>
          <Stack.Navigator initialRouteName={initialRoute}>
            <Stack.Screen
              name="PhoneEntry"
              component={PhoneEntryScreen}
              options={{ title: 'Driver Sign In' }}
            />
            <Stack.Screen
              name="OtpEntry"
              component={OtpEntryScreen}
              options={{ title: 'Verify OTP' }}
            />
            <Stack.Screen
              name="DriverHome"
              component={DriverHomeScreen}
              options={{ title: 'Driver Home' }}
            />
            <Stack.Screen
              name="QrScan"
              component={QrScanScreen}
              options={{ title: 'Scan QR' }}
            />
          </Stack.Navigator>
        </NavigationContainer>
      </SafeAreaProvider>
    </PaperProvider>
  );
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
});

import { useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { NavigationContainer } from '@react-navigation/native';
import { createNativeStackNavigator } from '@react-navigation/native-stack';
import { ActivityIndicator, PaperProvider } from 'react-native-paper';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { getStoredToken } from './src/auth';
import { ProtocolFlowProvider } from './src/navigation/ProtocolFlowContext';
import { RootStackParamList } from './src/navigation/types';
import DriverHomeScreen from './src/screens/DriverHomeScreen';
import IncidentConfirmScreen from './src/screens/IncidentConfirmScreen';
import IncidentStartLoadingScreen from './src/screens/IncidentStartLoadingScreen';
import IncidentStatusScreen from './src/screens/IncidentStatusScreen';
import InstructionStepScreen from './src/screens/InstructionStepScreen';
import MediaCaptureScreen from './src/screens/MediaCaptureScreen';
import NarrativeScreen from './src/screens/NarrativeScreen';
import OtpEntryScreen from './src/screens/OtpEntryScreen';
import PhoneEntryScreen from './src/screens/PhoneEntryScreen';
import QrScanScreen from './src/screens/QrScanScreen';
import ReviewSubmitScreen from './src/screens/ReviewSubmitScreen';
import SafetyGateScreen from './src/screens/SafetyGateScreen';
import SceneFactsScreen from './src/screens/SceneFactsScreen';
import ThirdPartyInfoScreen from './src/screens/ThirdPartyInfoScreen';
import VehicleConfirmScreen from './src/screens/VehicleConfirmScreen';

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
        <ProtocolFlowProvider>
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
                name="IncidentConfirm"
                component={IncidentConfirmScreen}
                options={{ title: 'Incident Confirmation' }}
              />
              <Stack.Screen
                name="VehicleConfirm"
                component={VehicleConfirmScreen}
                options={{ title: 'Vehicle Confirmation' }}
              />
              <Stack.Screen
                name="SafetyGate"
                component={SafetyGateScreen}
                options={{ title: 'Safety Gate' }}
              />
              <Stack.Screen
                name="IncidentStartLoading"
                component={IncidentStartLoadingScreen}
                options={{ title: 'Loading Incident' }}
              />
              <Stack.Screen
                name="InstructionStep"
                component={InstructionStepScreen}
                options={{ title: 'Instruction Step' }}
              />
              <Stack.Screen
                name="SceneFacts"
                component={SceneFactsScreen}
                options={{ title: 'Scene Facts' }}
              />
              <Stack.Screen
                name="ThirdPartyInfo"
                component={ThirdPartyInfoScreen}
                options={{ title: 'Third Party Info' }}
              />
              <Stack.Screen
                name="MediaCapture"
                component={MediaCaptureScreen}
                options={{ title: 'Media Capture' }}
              />
              <Stack.Screen
                name="Narrative"
                component={NarrativeScreen}
                options={{ title: 'Narrative' }}
              />
              <Stack.Screen
                name="ReviewSubmit"
                component={ReviewSubmitScreen}
                options={{ title: 'Review & Submit' }}
              />
              <Stack.Screen
                name="IncidentStatus"
                component={IncidentStatusScreen}
                options={{ title: 'Incident Status' }}
              />
              <Stack.Screen
                name="QrScan"
                component={QrScanScreen}
                options={{ title: 'Scan QR' }}
              />
            </Stack.Navigator>
          </NavigationContainer>
        </ProtocolFlowProvider>
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

import { useEffect } from 'react';
import { Linking, ScrollView, StyleSheet, View } from 'react-native';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Button, Text } from 'react-native-paper';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import {
  emitProtocolAnalyticsEvent,
  emitTimelineAndAnalyticsEvent,
} from '../telemetry/protocolEvents';

type Props = NativeStackScreenProps<RootStackParamList, 'SafetyGate'>;

const EMERGENCY_NUMBER = '911';
const SAFETY_MANAGER_NUMBER = '+18005551212';

export default function SafetyGateScreen({ navigation }: Props) {
  const {
    completeRoute,
    markSafetyGateViewed,
    acknowledgeSafetyGate,
    recordEmergencyCallTap,
    recordSafetyManagerCallTap,
    protocolContext,
  } = useProtocolFlow();

  useProtocolRouteGuard('SafetyGate', navigation);

  useEffect(() => {
    markSafetyGateViewed();
    emitTimelineAndAnalyticsEvent('driver_safety_gate_viewed');
  }, [markSafetyGateViewed]);

  const callNumber = async (number: string) => {
    await Linking.openURL(`tel:${number}`);
  };

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.content}>
        <Text variant="headlineMedium">Safety Gate</Text>
        <Text variant="bodyLarge" style={styles.description}>
          Confirm scene safety first. You must acknowledge this step before
          proceeding to incident capture.
        </Text>
        <View style={styles.callActions}>
          <Button
            mode="outlined"
            onPress={() => {
              recordEmergencyCallTap();
              emitTimelineAndAnalyticsEvent('driver_emergency_call_tapped');
              void callNumber(EMERGENCY_NUMBER);
            }}
          >
            Call 911
          </Button>
          <Button
            mode="outlined"
            onPress={() => {
              recordSafetyManagerCallTap();
              emitTimelineAndAnalyticsEvent('driver_safety_call_tapped');
              void callNumber(SAFETY_MANAGER_NUMBER);
            }}
          >
            Call Safety Manager
          </Button>
        </View>
      </View>

      <Button
        mode="contained"
        onPress={() => {
          acknowledgeSafetyGate();
          emitProtocolAnalyticsEvent('safety_gate_acknowledged', {
            workflowCorrelationId: protocolContext.workflowCorrelationId,
          });
          emitTimelineAndAnalyticsEvent('driver_safety_gate_acknowledged');
          completeRoute('SafetyGate');
          navigation.navigate('IncidentStartLoading');
        }}
      >
        Safety check complete
      </Button>
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
    gap: 12,
  },
  description: {
    color: '#5f6b7a',
  },
  callActions: {
    marginTop: 8,
    gap: 12,
  },
});

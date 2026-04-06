import { useCallback, useEffect, useMemo, useState } from 'react';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScrollView, StyleSheet, View } from 'react-native';
import { Button, Card, Chip, HelperText, Text } from 'react-native-paper';

import {
  DriverIncidentStatusResponse,
  getDriverActiveIncident,
  getDriverIncidentStatus,
  submitDriverIncidentReport,
} from '../api';
import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { PROTOCOL_ROUTE_ORDER, ProtocolRouteName } from '../navigation/protocolFlow';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import { emitProtocolAnalyticsEvent } from '../telemetry/protocolEvents';

type Props = NativeStackScreenProps<RootStackParamList, 'ReviewSubmit'>;

type ChecklistItem = {
  routeName: ProtocolRouteName;
  label: string;
  isComplete: boolean;
};

const COMPONENT_LABELS: Readonly<Record<ProtocolRouteName, string>> = {
  IncidentConfirm: 'Incident confirmed',
  VehicleConfirm: 'Vehicle confirmed',
  SafetyGate: 'Safety gate acknowledged',
  IncidentStartLoading: 'Incident start initialized',
  InstructionStep: 'Instruction steps acknowledged',
  SceneFacts: 'Scene facts captured',
  ThirdPartyInfo: 'Third-party info reviewed',
  MediaCapture: 'Media captured',
  Narrative: 'Narrative completed',
  ReviewSubmit: 'Review completed',
  IncidentStatus: 'Status reviewed',
};

const REVIEWABLE_ROUTES: ReadonlyArray<ProtocolRouteName> = PROTOCOL_ROUTE_ORDER.filter(
  (routeName) => routeName !== 'ReviewSubmit' && routeName !== 'IncidentStatus',
);

const MINIMUM_SUBMISSION_ROUTES: ReadonlyArray<ProtocolRouteName> = [
  'IncidentConfirm',
  'VehicleConfirm',
  'SafetyGate',
  'InstructionStep',
  'SceneFacts',
  'MediaCapture',
  'Narrative',
];

function describeUploadStatus(incidentStatus: DriverIncidentStatusResponse | null): string {
  if (!incidentStatus) {
    return 'Unknown';
  }

  switch (incidentStatus.capture_state) {
    case 'completed':
      return 'Uploaded';
    case 'in_progress':
      return 'Uploading';
    case 'failed':
      return 'Failed';
    case 'pending':
      return 'Pending';
    default:
      return incidentStatus.capture_state;
  }
}

export default function ReviewSubmitScreen({ navigation }: Props) {
  const { completeRoute, completedRoutes, protocolContext } = useProtocolFlow();
  useProtocolRouteGuard('ReviewSubmit', navigation);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingStatus, setIsLoadingStatus] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [incidentStatus, setIncidentStatus] =
    useState<DriverIncidentStatusResponse | null>(null);

  const checklistItems = useMemo<ChecklistItem[]>(
    () =>
      REVIEWABLE_ROUTES.map((routeName) => ({
        routeName,
        label: COMPONENT_LABELS[routeName],
        isComplete: completedRoutes.has(routeName),
      })),
    [completedRoutes],
  );

  const minimumSubmissionReady = useMemo(
    () => MINIMUM_SUBMISSION_ROUTES.every((routeName) => completedRoutes.has(routeName)),
    [completedRoutes],
  );

  useEffect(() => {
    const loadUploadStatus = async () => {
      setIsLoadingStatus(true);

      try {
        const activeIncident = await getDriverActiveIncident();
        const incidentId = activeIncident?.incident_id?.trim();

        if (!incidentId) {
          setIncidentStatus(null);
          return;
        }

        const status = await getDriverIncidentStatus(incidentId);
        setIncidentStatus(status);
      } catch {
        setIncidentStatus(null);
      } finally {
        setIsLoadingStatus(false);
      }
    };

    void loadUploadStatus();
  }, []);

  const uploadStatusLabel = useMemo(
    () => describeUploadStatus(incidentStatus),
    [incidentStatus],
  );

  const saveAndFinishLater = useCallback(() => {
    completeRoute('ReviewSubmit');
    navigation.navigate('IncidentStatus');
  }, [completeRoute, navigation]);

  const handleSubmit = useCallback(async () => {
    setErrorText(null);

    if (!minimumSubmissionReady) {
      setErrorText('Minimum requirements are not complete. Finish required workflow components.');
      return;
    }

    setIsSubmitting(true);

    try {
      const activeIncident = await getDriverActiveIncident();
      const incidentId = activeIncident?.incident_id?.trim();
      if (!incidentId) {
        setErrorText('No active incident found to submit.');
        return;
      }

      const incidentStatus = await getDriverIncidentStatus(incidentId);
      if (incidentStatus.capture_state === 'failed') {
        setErrorText('Uploads failed. Retry media upload before submitting.');
        return;
      }

      await submitDriverIncidentReport(incidentId);
      emitProtocolAnalyticsEvent('driver_report_submitted', {
        incidentId,
        workflowCorrelationId: protocolContext.workflowCorrelationId,
      });
      completeRoute('ReviewSubmit');
      navigation.navigate('IncidentStatus');
    } catch (error) {
      setErrorText(error instanceof Error ? error.message : 'Unable to submit incident report.');
    } finally {
      setIsSubmitting(false);
    }
  }, [
    completeRoute,
    minimumSubmissionReady,
    navigation,
    protocolContext.workflowCorrelationId,
  ]);

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.headerBlock}>
        <Text variant="headlineSmall">Review & Submit</Text>
        <Text variant="bodyMedium" style={styles.description}>
          Confirm the workflow checklist and upload status, then submit your incident report.
        </Text>
      </View>

      <Card>
        <Card.Title title="Workflow checklist" />
        <Card.Content style={styles.sectionContent}>
          {checklistItems.map((item) => (
            <View style={styles.checklistRow} key={item.routeName}>
              <Text>{item.label}</Text>
              <Chip selected={item.isComplete}>{item.isComplete ? 'Complete' : 'Pending'}</Chip>
            </View>
          ))}
        </Card.Content>
      </Card>

      <Card>
        <Card.Title title="Submission readiness" />
        <Card.Content style={styles.sectionContent}>
          <Text>
            Minimum requirements: {minimumSubmissionReady ? 'Ready' : 'Pending required components'}
          </Text>
          <Text>
            This submit gate enforces minimum requirements only, not perfect completeness.
          </Text>
          <Text>
            Upload status: {isLoadingStatus ? 'Loading…' : uploadStatusLabel}.
          </Text>
          <Text>Uploads must not be in a failed state for submission.</Text>
        </Card.Content>
      </Card>

      {errorText ? <HelperText type="error">{errorText}</HelperText> : null}

      <View style={styles.actions}>
        <Button mode="outlined" onPress={() => navigation.goBack()} disabled={isSubmitting}>
          Back
        </Button>
        <Button
          mode="outlined"
          onPress={saveAndFinishLater}
          disabled={isSubmitting}
        >
          Save and Finish Later
        </Button>
        <Button mode="contained" onPress={() => void handleSubmit()} loading={isSubmitting}>
          Submit Incident Report
        </Button>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    gap: 16,
    padding: 24,
  },
  headerBlock: {
    gap: 6,
  },
  description: {
    color: '#5f6b7a',
  },
  sectionContent: {
    gap: 10,
  },
  checklistRow: {
    alignItems: 'center',
    flexDirection: 'row',
    justifyContent: 'space-between',
    gap: 8,
  },
  actions: {
    gap: 12,
    marginTop: 'auto',
  },
});

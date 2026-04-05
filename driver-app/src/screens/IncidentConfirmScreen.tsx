import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import { emitTimelineAndAnalyticsEvent } from '../telemetry/protocolEvents';
import ProtocolStepScreen from './ProtocolStepScreen';

type Props = NativeStackScreenProps<RootStackParamList, 'IncidentConfirm'>;

export default function IncidentConfirmScreen({ navigation }: Props) {
  const { completeRoute, transitionWorkflow } = useProtocolFlow();
  useProtocolRouteGuard('IncidentConfirm', navigation);

  return (
    <ProtocolStepScreen
      title="Confirm Incident"
      description="Confirm this is the right moment to launch the incident protocol and begin evidence capture."
      continueLabel="Continue"
      onContinue={() => {
        transitionWorkflow('incident_confirmed');
        emitTimelineAndAnalyticsEvent('driver_protocol_launch_confirmed');
        completeRoute('IncidentConfirm');
        navigation.navigate('VehicleConfirm');
      }}
      backLabel="Cancel"
      onBack={() => navigation.navigate('DriverHome')}
    />
  );
}

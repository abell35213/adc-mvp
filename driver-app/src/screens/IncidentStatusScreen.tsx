import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import ProtocolStepScreen from './ProtocolStepScreen';

type Props = NativeStackScreenProps<RootStackParamList, 'IncidentStatus'>;

export default function IncidentStatusScreen({ navigation }: Props) {
  const { completeRoute, resetProtocol } = useProtocolFlow();
  useProtocolRouteGuard('IncidentStatus', navigation);

  return (
    <ProtocolStepScreen
      title="Incident Status"
      description="Your incident has been submitted. Return to home for the next task."
      continueLabel="Return to home"
      onContinue={() => {
        completeRoute('IncidentStatus');
        resetProtocol();
        navigation.reset({ index: 0, routes: [{ name: 'DriverHome' }] });
      }}
      onBack={() => navigation.goBack()}
    />
  );
}

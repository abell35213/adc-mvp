import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import ProtocolStepScreen from './ProtocolStepScreen';

type Props = NativeStackScreenProps<RootStackParamList, 'SafetyGate'>;

export default function SafetyGateScreen({ navigation }: Props) {
  const { completeRoute } = useProtocolFlow();
  useProtocolRouteGuard('SafetyGate', navigation);

  return (
    <ProtocolStepScreen
      title="Safety Gate"
      description="Complete the immediate safety checklist before loading incident steps."
      continueLabel="Safety check complete"
      onContinue={() => {
        completeRoute('SafetyGate');
        navigation.navigate('IncidentStartLoading');
      }}
      onBack={() => navigation.goBack()}
    />
  );
}

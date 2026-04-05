import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import ProtocolStepScreen from './ProtocolStepScreen';

type Props = NativeStackScreenProps<RootStackParamList, 'IncidentStartLoading'>;

export default function IncidentStartLoadingScreen({ navigation }: Props) {
  const { completeRoute } = useProtocolFlow();
  useProtocolRouteGuard('IncidentStartLoading', navigation);

  return (
    <ProtocolStepScreen
      title="Start Incident Loading"
      description="Prepare protocol instructions and wait for loading to complete."
      continueLabel="Continue"
      onContinue={() => {
        completeRoute('IncidentStartLoading');
        navigation.navigate('InstructionStep');
      }}
      onBack={() => navigation.goBack()}
    />
  );
}

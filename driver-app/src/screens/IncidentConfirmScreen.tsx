import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import ProtocolStepScreen from './ProtocolStepScreen';

type Props = NativeStackScreenProps<RootStackParamList, 'IncidentConfirm'>;

export default function IncidentConfirmScreen({ navigation }: Props) {
  const { completeRoute } = useProtocolFlow();
  useProtocolRouteGuard('IncidentConfirm', navigation);

  return (
    <ProtocolStepScreen
      title="Confirm Incident"
      description="Verify this incident is valid and should enter the protocol workflow."
      continueLabel="Confirm incident"
      onContinue={() => {
        completeRoute('IncidentConfirm');
        navigation.navigate('VehicleConfirm');
      }}
      backLabel="Back to home"
      onBack={() => navigation.navigate('DriverHome')}
    />
  );
}

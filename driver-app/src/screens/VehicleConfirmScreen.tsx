import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import ProtocolStepScreen from './ProtocolStepScreen';

type Props = NativeStackScreenProps<RootStackParamList, 'VehicleConfirm'>;

export default function VehicleConfirmScreen({ navigation }: Props) {
  const { completeRoute } = useProtocolFlow();
  useProtocolRouteGuard('VehicleConfirm', navigation);

  return (
    <ProtocolStepScreen
      title="Confirm Vehicle"
      description="Confirm you are reporting for the correct vehicle before continuing."
      continueLabel="Vehicle confirmed"
      onContinue={() => {
        completeRoute('VehicleConfirm');
        navigation.navigate('SafetyGate');
      }}
      onBack={() => navigation.goBack()}
    />
  );
}

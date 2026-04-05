import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import ProtocolStepScreen from './ProtocolStepScreen';

type Props = NativeStackScreenProps<RootStackParamList, 'InstructionStep'>;

export default function InstructionStepScreen({ navigation }: Props) {
  const { completeRoute } = useProtocolFlow();
  useProtocolRouteGuard('InstructionStep', navigation);

  return (
    <ProtocolStepScreen
      title="Instruction Step"
      description="Follow the dispatch instruction and confirm completion."
      continueLabel="Instruction complete"
      onContinue={() => {
        completeRoute('InstructionStep');
        navigation.navigate('SceneFacts');
      }}
      onBack={() => navigation.goBack()}
    />
  );
}

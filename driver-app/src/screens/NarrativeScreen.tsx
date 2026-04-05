import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import ProtocolStepScreen from './ProtocolStepScreen';

type Props = NativeStackScreenProps<RootStackParamList, 'Narrative'>;

export default function NarrativeScreen({ navigation }: Props) {
  const { completeRoute } = useProtocolFlow();
  useProtocolRouteGuard('Narrative', navigation);

  return (
    <ProtocolStepScreen
      title="Narrative"
      description="Provide your narrative summary before final review and submission."
      continueLabel="Narrative complete"
      onContinue={() => {
        completeRoute('Narrative');
        navigation.navigate('ReviewSubmit');
      }}
      onBack={() => navigation.goBack()}
    />
  );
}

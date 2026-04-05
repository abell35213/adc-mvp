import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import ProtocolStepScreen from './ProtocolStepScreen';

type Props = NativeStackScreenProps<RootStackParamList, 'ReviewSubmit'>;

export default function ReviewSubmitScreen({ navigation }: Props) {
  const { completeRoute } = useProtocolFlow();
  useProtocolRouteGuard('ReviewSubmit', navigation);

  return (
    <ProtocolStepScreen
      title="Review & Submit"
      description="Review all protocol details and submit the incident packet."
      continueLabel="Submit incident"
      onContinue={() => {
        completeRoute('ReviewSubmit');
        navigation.navigate('IncidentStatus');
      }}
      onBack={() => navigation.goBack()}
    />
  );
}

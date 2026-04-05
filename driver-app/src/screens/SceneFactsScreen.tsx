import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import ProtocolStepScreen from './ProtocolStepScreen';

type Props = NativeStackScreenProps<RootStackParamList, 'SceneFacts'>;

export default function SceneFactsScreen({ navigation }: Props) {
  const { completeRoute } = useProtocolFlow();
  useProtocolRouteGuard('SceneFacts', navigation);

  return (
    <ProtocolStepScreen
      title="Scene Facts"
      description="Capture key facts from the scene before collecting third-party details."
      continueLabel="Facts recorded"
      onContinue={() => {
        completeRoute('SceneFacts');
        navigation.navigate('ThirdPartyInfo');
      }}
      onBack={() => navigation.goBack()}
    />
  );
}

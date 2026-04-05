import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import ProtocolStepScreen from './ProtocolStepScreen';

type Props = NativeStackScreenProps<RootStackParamList, 'ThirdPartyInfo'>;

export default function ThirdPartyInfoScreen({ navigation }: Props) {
  const { completeRoute } = useProtocolFlow();
  useProtocolRouteGuard('ThirdPartyInfo', navigation);

  return (
    <ProtocolStepScreen
      title="Third Party Info"
      description="Collect details for involved third parties before media capture."
      continueLabel="Third-party info saved"
      onContinue={() => {
        completeRoute('ThirdPartyInfo');
        navigation.navigate('MediaCapture');
      }}
      onBack={() => navigation.goBack()}
    />
  );
}

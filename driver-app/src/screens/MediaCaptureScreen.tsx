import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import ProtocolStepScreen from './ProtocolStepScreen';

type Props = NativeStackScreenProps<RootStackParamList, 'MediaCapture'>;

export default function MediaCaptureScreen({ navigation }: Props) {
  const { completeRoute } = useProtocolFlow();
  useProtocolRouteGuard('MediaCapture', navigation);

  return (
    <ProtocolStepScreen
      title="Media Capture"
      description="Capture photos and videos before writing the incident narrative."
      continueLabel="Media captured"
      onContinue={() => {
        completeRoute('MediaCapture');
        navigation.navigate('Narrative');
      }}
      onBack={() => navigation.goBack()}
    />
  );
}

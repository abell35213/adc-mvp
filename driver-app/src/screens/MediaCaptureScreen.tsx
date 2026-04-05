import { NativeStackScreenProps } from '@react-navigation/native-stack';

import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import ProtocolStepScreen from './ProtocolStepScreen';

type Props = NativeStackScreenProps<RootStackParamList, 'MediaCapture'>;

export default function MediaCaptureScreen({ navigation, route }: Props) {
  const { completeRoute } = useProtocolFlow();
  useProtocolRouteGuard('MediaCapture', navigation);
  const promptType = route.params?.destinationPromptType;

  const destinationHint =
    promptType === 'third_party_vehicle'
      ? 'Next capture hint: focus on third-party vehicle identifiers.'
      : promptType === 'third_party_document'
        ? 'Next capture hint: focus on third-party insurance/ID documents.'
        : 'Next capture hint: capture broad scene and damage media.';

  return (
    <ProtocolStepScreen
      title="Media Capture"
      description={`Capture photos and videos before writing the incident narrative.\n\n${destinationHint}`}
      continueLabel="Media captured"
      onContinue={() => {
        completeRoute('MediaCapture');
        navigation.navigate('Narrative');
      }}
      onBack={() => navigation.goBack()}
    />
  );
}

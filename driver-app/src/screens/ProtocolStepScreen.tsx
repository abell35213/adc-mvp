import { ScrollView, StyleSheet, View } from 'react-native';
import { Button, Text } from 'react-native-paper';

type ProtocolStepScreenProps = {
  title: string;
  description: string;
  continueLabel: string;
  onContinue: () => void;
  backLabel?: string;
  onBack?: () => void;
};

export default function ProtocolStepScreen({
  title,
  description,
  continueLabel,
  onContinue,
  backLabel,
  onBack,
}: ProtocolStepScreenProps) {
  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.content}>
        <Text variant="headlineMedium">{title}</Text>
        <Text variant="bodyLarge" style={styles.description}>
          {description}
        </Text>
      </View>

      <View style={styles.actions}>
        {onBack ? (
          <Button mode="outlined" onPress={onBack}>
            {backLabel ?? 'Back'}
          </Button>
        ) : null}
        <Button mode="contained" onPress={onContinue}>
          {continueLabel}
        </Button>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    justifyContent: 'space-between',
    padding: 24,
    gap: 24,
  },
  content: {
    gap: 12,
  },
  description: {
    color: '#5f6b7a',
  },
  actions: {
    gap: 12,
  },
});

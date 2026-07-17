import { useCallback, useEffect, useMemo, useState } from 'react';
import { NativeStackScreenProps } from '@react-navigation/native-stack';
import { ScrollView, StyleSheet, View } from 'react-native';
import { ActivityIndicator, Button, Text } from 'react-native-paper';
import AsyncStorage from '@react-native-async-storage/async-storage';

import {
  acknowledgeDriverInstructions,
  DriverInstructionStepResponse,
  getDriverActiveInstructions,
} from '../api';
import { useProtocolFlow } from '../navigation/ProtocolFlowContext';
import { RootStackParamList } from '../navigation/types';
import { useProtocolRouteGuard } from '../navigation/useProtocolRouteGuard';
import {
  emitProtocolAnalyticsEvent,
  emitTimelineAndAnalyticsEvent,
} from '../telemetry/protocolEvents';

type Props = NativeStackScreenProps<RootStackParamList, 'InstructionStep'>;

type StoredInstructionProgress = {
  instructionSetId: string;
  viewedStepIds: string[];
  acknowledgedStepIds: string[];
  currentStepIndex: number;
};

type ActiveInstructionSet = {
  instruction_set_id: string;
  require_ack: boolean;
  steps: DriverInstructionStepResponse[];
};

const INSTRUCTION_PROGRESS_STORAGE_KEY = 'driver_instruction_progress_v1';

function normalizeStepOrder(steps: DriverInstructionStepResponse[]) {
  return [...steps].sort((left, right) => left.step_order - right.step_order);
}

function clampStepIndex(stepIndex: unknown, stepCount: number) {
  if (typeof stepIndex !== 'number' || !Number.isFinite(stepIndex)) {
    return 0;
  }

  return Math.max(0, Math.min(Math.trunc(stepIndex), stepCount - 1));
}

function toValidStepIdSet(stepIds: unknown, validStepIds: Set<string>) {
  if (!Array.isArray(stepIds)) {
    return new Set<string>();
  }

  return new Set(
    stepIds.filter(
      (stepId): stepId is string =>
        typeof stepId === 'string' && validStepIds.has(stepId),
    ),
  );
}

export default function InstructionStepScreen({ navigation }: Props) {
  const { completeRoute, protocolContext } = useProtocolFlow();
  useProtocolRouteGuard('InstructionStep', navigation);

  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [activeSet, setActiveSet] = useState<ActiveInstructionSet | null>(null);
  const [currentStepIndex, setCurrentStepIndex] = useState(0);
  const [viewedStepIds, setViewedStepIds] = useState<Set<string>>(new Set());
  const [acknowledgedStepIds, setAcknowledgedStepIds] = useState<Set<string>>(
    new Set(),
  );
  const [isAcknowledging, setIsAcknowledging] = useState(false);

  const persistProgress = useCallback(
    async (
      instructionSetId: string,
      nextStepIndex: number,
      nextViewedStepIds: Set<string>,
      nextAcknowledgedStepIds: Set<string>,
    ) => {
      const payload: StoredInstructionProgress = {
        instructionSetId,
        currentStepIndex: nextStepIndex,
        viewedStepIds: Array.from(nextViewedStepIds),
        acknowledgedStepIds: Array.from(nextAcknowledgedStepIds),
      };
      await AsyncStorage.setItem(
        INSTRUCTION_PROGRESS_STORAGE_KEY,
        JSON.stringify(payload),
      );
    },
    [],
  );

  const markStepViewed = useCallback(
    async (
      stepId: string,
      instructionSetId: string,
      stepIndex: number,
      currentAcknowledgedStepIds: Set<string>,
    ) => {
      if (viewedStepIds.has(stepId)) {
        return;
      }

      const nextViewedStepIds = new Set(viewedStepIds);
      nextViewedStepIds.add(stepId);
      setViewedStepIds(nextViewedStepIds);
      emitTimelineAndAnalyticsEvent('driver_instruction_step_viewed');

      await persistProgress(
        instructionSetId,
        stepIndex,
        nextViewedStepIds,
        currentAcknowledgedStepIds,
      );
    },
    [persistProgress, viewedStepIds],
  );

  const loadActiveInstructions = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);

    try {
      const response = await getDriverActiveInstructions();
      const normalizedSteps = normalizeStepOrder(response.steps ?? []);
      const requireAck = Boolean(response.require_ack);
      const nextActiveSet: ActiveInstructionSet = {
        instruction_set_id: response.instruction_set_id,
        require_ack: requireAck,
        steps: normalizedSteps,
      };

      if (!normalizedSteps.length) {
        completeRoute('InstructionStep');
        navigation.replace('SceneFacts');
        return;
      }

      const validStepIds = new Set(normalizedSteps.map((step) => step.step_id));
      const storedRaw = await AsyncStorage.getItem(
        INSTRUCTION_PROGRESS_STORAGE_KEY,
      );
      let nextStepIndex = 0;
      let nextViewedStepIds = new Set<string>();
      let nextAcknowledgedStepIds = new Set<string>();

      if (storedRaw) {
        try {
          const stored = JSON.parse(storedRaw) as StoredInstructionProgress;
          if (stored.instructionSetId === response.instruction_set_id) {
            nextStepIndex = clampStepIndex(
              stored.currentStepIndex,
              normalizedSteps.length,
            );
            nextViewedStepIds = toValidStepIdSet(
              stored.viewedStepIds,
              validStepIds,
            );
            nextAcknowledgedStepIds = toValidStepIdSet(
              stored.acknowledgedStepIds,
              validStepIds,
            );
          }
        } catch {
          // Ignore malformed local progress state and reset to defaults.
        }
      }

      const initialStep = normalizedSteps[nextStepIndex];
      const shouldMarkInitialStepViewed = !nextViewedStepIds.has(
        initialStep.step_id,
      );
      if (shouldMarkInitialStepViewed) {
        nextViewedStepIds = new Set(nextViewedStepIds);
        nextViewedStepIds.add(initialStep.step_id);
      }

      setActiveSet(nextActiveSet);
      setCurrentStepIndex(nextStepIndex);
      setViewedStepIds(nextViewedStepIds);
      setAcknowledgedStepIds(nextAcknowledgedStepIds);

      if (shouldMarkInitialStepViewed) {
        emitTimelineAndAnalyticsEvent('driver_instruction_step_viewed');
        await persistProgress(
          response.instruction_set_id,
          nextStepIndex,
          nextViewedStepIds,
          nextAcknowledgedStepIds,
        );
      }
    } catch (error) {
      setLoadError(
        error instanceof Error
          ? error.message
          : 'Failed to load active instructions.',
      );
    } finally {
      setIsLoading(false);
    }
  }, [completeRoute, navigation, persistProgress]);

  useEffect(() => {
    void loadActiveInstructions();
  }, [loadActiveInstructions]);

  const currentStep = useMemo(() => {
    if (!activeSet?.steps.length) {
      return null;
    }

    return activeSet.steps[currentStepIndex] ?? null;
  }, [activeSet, currentStepIndex]);

  const isCurrentStepAcknowledged =
    currentStep != null && acknowledgedStepIds.has(currentStep.step_id);
  const shouldDisableNext =
    Boolean(activeSet?.require_ack) &&
    currentStep != null &&
    !isCurrentStepAcknowledged;

  const handleAcknowledgeStep = useCallback(async () => {
    if (!activeSet || !currentStep || isCurrentStepAcknowledged) {
      return;
    }

    setIsAcknowledging(true);
    setLoadError(null);
    try {
      await acknowledgeDriverInstructions(activeSet.instruction_set_id);
      emitProtocolAnalyticsEvent('instruction_acknowledged', {
        workflowCorrelationId: protocolContext.workflowCorrelationId,
        payload: {
          instruction_set_id: activeSet.instruction_set_id,
          instruction_step_id: currentStep.step_id,
        },
      });
      const nextAcknowledgedStepIds = new Set(acknowledgedStepIds);
      nextAcknowledgedStepIds.add(currentStep.step_id);
      setAcknowledgedStepIds(nextAcknowledgedStepIds);
      await persistProgress(
        activeSet.instruction_set_id,
        currentStepIndex,
        viewedStepIds,
        nextAcknowledgedStepIds,
      );
    } catch (error) {
      setLoadError(
        error instanceof Error
          ? error.message
          : 'Unable to acknowledge this step.',
      );
    } finally {
      setIsAcknowledging(false);
    }
  }, [
    activeSet,
    acknowledgedStepIds,
    currentStep,
    currentStepIndex,
    isCurrentStepAcknowledged,
    persistProgress,
    protocolContext.workflowCorrelationId,
    viewedStepIds,
  ]);

  const handleContinue = useCallback(async () => {
    if (!activeSet || !currentStep || shouldDisableNext) {
      return;
    }

    const isLastStep = currentStepIndex >= activeSet.steps.length - 1;
    if (isLastStep) {
      completeRoute('InstructionStep');
      navigation.navigate('SceneFacts');
      return;
    }

    const nextStepIndex = currentStepIndex + 1;
    const nextStep = activeSet.steps[nextStepIndex];
    setCurrentStepIndex(nextStepIndex);

    await markStepViewed(
      nextStep.step_id,
      activeSet.instruction_set_id,
      nextStepIndex,
      acknowledgedStepIds,
    );
  }, [
    acknowledgedStepIds,
    activeSet,
    completeRoute,
    currentStep,
    currentStepIndex,
    markStepViewed,
    navigation,
    shouldDisableNext,
  ]);

  if (isLoading) {
    return (
      <View style={styles.stateContainer}>
        <ActivityIndicator animating size="large" />
        <Text variant="bodyMedium">Loading active instructions…</Text>
      </View>
    );
  }

  if (loadError && !activeSet) {
    return (
      <View style={styles.stateContainer}>
        <Text variant="titleMedium">Unable to load instructions</Text>
        <Text variant="bodyMedium" style={styles.errorText}>
          {loadError}
        </Text>
        <Button mode="contained" onPress={() => void loadActiveInstructions()}>
          Retry
        </Button>
      </View>
    );
  }

  if (!currentStep || !activeSet) {
    return (
      <View style={styles.stateContainer}>
        <Text variant="bodyLarge">No instructions available.</Text>
        <Button
          mode="contained"
          onPress={() => navigation.navigate('SceneFacts')}
        >
          Continue
        </Button>
      </View>
    );
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <View style={styles.content}>
        <Text variant="headlineSmall">Instruction step</Text>
        <Text variant="labelLarge" style={styles.metaText}>
          Step {currentStepIndex + 1} of {activeSet.steps.length}
        </Text>
        <Text variant="titleLarge">{currentStep.title}</Text>
        <Text variant="bodyLarge" style={styles.description}>
          {currentStep.body}
        </Text>
        {loadError ? (
          <Text variant="bodySmall" style={styles.errorText}>
            {loadError}
          </Text>
        ) : null}
      </View>

      <View style={styles.actions}>
        {activeSet.require_ack ? (
          <Button
            mode={isCurrentStepAcknowledged ? 'contained-tonal' : 'outlined'}
            onPress={() => void handleAcknowledgeStep()}
            disabled={isCurrentStepAcknowledged || isAcknowledging}
            loading={isAcknowledging}
          >
            {isCurrentStepAcknowledged ? 'Acknowledged' : 'Acknowledge step'}
          </Button>
        ) : null}

        <Button mode="outlined" onPress={() => navigation.goBack()}>
          Back
        </Button>
        <Button
          mode="contained"
          onPress={() => void handleContinue()}
          disabled={shouldDisableNext}
        >
          {currentStepIndex >= activeSet.steps.length - 1 ? 'Continue' : 'Next'}
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
  metaText: {
    color: '#5f6b7a',
  },
  actions: {
    gap: 12,
  },
  stateContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
    gap: 12,
  },
  errorText: {
    color: '#b3261e',
    textAlign: 'center',
  },
});

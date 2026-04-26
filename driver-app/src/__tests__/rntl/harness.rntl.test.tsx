/**
 * Smoke test for the RNTL test harness.
 *
 * Renders a trivial React Native + react-native-paper tree to verify:
 *   1. The ``jest-expo`` preset loads correctly (jsdom + RN transformer).
 *   2. ``@testing-library/react-native`` queries return a node.
 *   3. ``react-native-paper`` and the Reanimated mock co-exist without
 *      throwing during module evaluation.
 *
 * If this test fails, no other RNTL screen test will pass — fix here
 * first before investigating individual screen suites.
 */

import { render, screen } from '@testing-library/react-native';
import { Text } from 'react-native';
import { PaperProvider } from 'react-native-paper';

describe('RNTL harness', () => {
  it('renders a minimal Paper-wrapped tree', () => {
    render(
      <PaperProvider>
        <Text>hello driver</Text>
      </PaperProvider>,
    );

    expect(screen.getByText('hello driver')).toBeOnTheScreen();
  });

  it('matches a stable snapshot for the trivial tree', () => {
    const tree = render(
      <PaperProvider>
        <Text testID="harness-text">hello driver</Text>
      </PaperProvider>,
    ).toJSON();

    expect(tree).toMatchSnapshot();
  });
});

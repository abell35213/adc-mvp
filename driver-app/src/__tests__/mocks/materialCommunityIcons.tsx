/**
 * Test-only stub for `@expo/vector-icons/MaterialCommunityIcons`.
 *
 * The real module pulls in `expo-font` → `expo-asset` → `expo-modules-core`,
 * none of which resolve cleanly inside the `jest-expo` jsdom environment used
 * by the rntl suite. The production app loads the real module without issue;
 * tests only need a deterministic stand-in that renders the icon name as
 * accessible text and accepts the same prop shape.
 */

import * as React from 'react';
import { Text } from 'react-native';

type Props = {
  name?: string;
  color?: string;
  size?: number;
  testID?: string;
};

const MaterialCommunityIconsStub = ({ name, color, size, testID }: Props) => (
  <Text
    testID={testID}
    accessibilityLabel={name}
    style={{ color, fontSize: size }}
  >
    {name ?? ''}
  </Text>
);

export default MaterialCommunityIconsStub;

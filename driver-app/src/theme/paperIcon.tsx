/**
 * `paperSettings` — explicit `react-native-paper` settings that pin the icon
 * provider to `@expo/vector-icons/MaterialCommunityIcons`.
 *
 * Why this exists:
 *
 * Paper's auto-detection (`require('@react-native-vector-icons/...')` →
 * `require('@expo/vector-icons/MaterialCommunityIcons')` →
 * `require('react-native-vector-icons/MaterialCommunityIcons')`) is wrapped in
 * try/catch.  In Jest's `jest-expo` jsdom environment those `require`s throw,
 * Paper falls back to a `□` placeholder, and emits the well-known
 * "Tried to use the icon … but none of the required icon libraries are
 * installed." warning.  The same warning is visible at runtime any time Paper
 * tries to render an icon (`<Checkbox/>`, `<Button icon=…/>`, etc.) before
 * Expo's vector-icons font has been resolved.
 *
 * Pinning the icon provider via {@link PaperProvider}'s `settings` prop bypasses
 * the brittle auto-detection and gives us a single, deterministic icon source
 * shared by the app and its tests.
 */

import * as React from 'react';
import MaterialCommunityIcons from '@expo/vector-icons/MaterialCommunityIcons';

type PaperIconProps = {
  name: string;
  color: string;
  size: number;
  direction?: 'ltr' | 'rtl';
  testID?: string;
};

const renderPaperIcon = ({
  name,
  color,
  size,
  testID,
}: PaperIconProps): React.ReactNode => (
  <MaterialCommunityIcons
    name={name as React.ComponentProps<typeof MaterialCommunityIcons>['name']}
    color={color}
    size={size}
    testID={testID}
  />
);

export const paperSettings = {
  icon: renderPaperIcon,
};

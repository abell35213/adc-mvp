import { useCallback } from 'react';
import { useFocusEffect } from '@react-navigation/native';

import {
  canAccessProtocolRoute,
  getFirstIncompleteRoute,
  ProtocolRouteName,
} from './protocolFlow';
import { useProtocolFlow } from './ProtocolFlowContext';

type ProtocolGuardNavigation = {
  replace: (routeName: ProtocolRouteName) => void;
};

export function useProtocolRouteGuard(
  routeName: ProtocolRouteName,
  navigation: ProtocolGuardNavigation,
) {
  const { completedRoutes } = useProtocolFlow();

  useFocusEffect(
    useCallback(() => {
      if (canAccessProtocolRoute(routeName, completedRoutes)) {
        return;
      }

      const firstIncompleteRoute = getFirstIncompleteRoute(completedRoutes);
      if (firstIncompleteRoute !== routeName) {
        navigation.replace(firstIncompleteRoute);
      }
    }, [completedRoutes, navigation, routeName]),
  );
}

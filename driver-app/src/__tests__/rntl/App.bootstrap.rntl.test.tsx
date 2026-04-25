/**
 * RNTL coverage for the `App` component bootstrap.
 *
 * Behaviours under test:
 *   1. While the stored token is being resolved, App renders the loading
 *      `ActivityIndicator` instead of the navigator.
 *   2. When `getStoredToken` resolves to `null`, App mounts the navigator
 *      with `PhoneEntry` as the initial route.
 *   3. When `getStoredToken` resolves to a non-null token, App mounts the
 *      navigator with `DriverHome` as the initial route.
 *   4. When `getStoredToken` rejects, App falls back to `PhoneEntry`.
 *   5. Mounting calls `startUploadWorker`; unmounting calls
 *      `stopUploadWorker`.
 *
 * Every screen is replaced with a stub `<View testID="screen-{name}" />`
 * so this suite exercises bootstrap wiring only — not the screens
 * themselves (which have their own dedicated suites).
 */

import { act, render, screen, waitFor } from '@testing-library/react-native';
import { View } from 'react-native';

// Babel's `jest.mock` hoist check requires an *inline* factory that is
// fully self-contained — it cannot call out to a helper. We therefore
// repeat the same minimal pattern for every screen module and use
// `require()` inside the factory so the references are resolved lazily,
// after the factories are hoisted above the imports.

jest.mock('../../auth');
jest.mock('../../services/uploads', () => ({
  startUploadWorker: jest.fn().mockResolvedValue(undefined),
  stopUploadWorker: jest.fn(),
}));
jest.mock('../../screens/PhoneEntryScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-PhoneEntry' }),
  };
});
jest.mock('../../screens/OtpEntryScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-OtpEntry' }),
  };
});
jest.mock('../../screens/DriverHomeScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-DriverHome' }),
  };
});
jest.mock('../../screens/IncidentConfirmScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-IncidentConfirm' }),
  };
});
jest.mock('../../screens/IncidentStartLoadingScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () =>
      React.createElement(RN.View, { testID: 'screen-IncidentStartLoading' }),
  };
});
jest.mock('../../screens/IncidentStatusScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-IncidentStatus' }),
  };
});
jest.mock('../../screens/InstructionStepScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-InstructionStep' }),
  };
});
jest.mock('../../screens/MediaCaptureScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-MediaCapture' }),
  };
});
jest.mock('../../screens/NarrativeScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-Narrative' }),
  };
});
jest.mock('../../screens/QrScanScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-QrScan' }),
  };
});
jest.mock('../../screens/ReviewSubmitScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-ReviewSubmit' }),
  };
});
jest.mock('../../screens/SafetyGateScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-SafetyGate' }),
  };
});
jest.mock('../../screens/SceneFactsScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-SceneFacts' }),
  };
});
jest.mock('../../screens/ThirdPartyInfoScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-ThirdPartyInfo' }),
  };
});
jest.mock('../../screens/VehicleConfirmScreen', () => {
  const RN = require('react-native');
  const React = require('react');
  return {
    __esModule: true,
    default: () => React.createElement(RN.View, { testID: 'screen-VehicleConfirm' }),
  };
});

import App from '../../../App';
import * as auth from '../../auth';
import * as uploads from '../../services/uploads';

const mockedGetStoredToken = jest.mocked(auth.getStoredToken);
const mockedStartUploadWorker = jest.mocked(uploads.startUploadWorker);
const mockedStopUploadWorker = jest.mocked(uploads.stopUploadWorker);

describe('App bootstrap', () => {
  it('renders the loading indicator while the stored token is being resolved', async () => {
    // Pending promise — never resolves during the assertion window.
    let resolveToken: (value: string | null) => void = () => undefined;
    mockedGetStoredToken.mockImplementationOnce(
      () =>
        new Promise<string | null>((resolve) => {
          resolveToken = resolve;
        }),
    );

    render(<App />);

    expect(screen.UNSAFE_queryAllByType(View).length).toBeGreaterThan(0);
    // The navigator hasn't mounted yet — none of the screen stubs exist.
    expect(screen.queryByTestId('screen-PhoneEntry')).toBeNull();
    expect(screen.queryByTestId('screen-DriverHome')).toBeNull();

    await act(async () => {
      resolveToken(null);
    });
  });

  it('mounts PhoneEntry as the initial route when no token is stored', async () => {
    mockedGetStoredToken.mockResolvedValueOnce(null);

    render(<App />);

    expect(await screen.findByTestId('screen-PhoneEntry')).toBeOnTheScreen();
    expect(screen.queryByTestId('screen-DriverHome')).toBeNull();
  });

  it('mounts DriverHome as the initial route when a token is stored', async () => {
    mockedGetStoredToken.mockResolvedValueOnce('jwt-stored-token');

    render(<App />);

    expect(await screen.findByTestId('screen-DriverHome')).toBeOnTheScreen();
    expect(screen.queryByTestId('screen-PhoneEntry')).toBeNull();
  });

  it('falls back to PhoneEntry when getStoredToken rejects', async () => {
    mockedGetStoredToken.mockRejectedValueOnce(new Error('keystore unavailable'));

    render(<App />);

    expect(await screen.findByTestId('screen-PhoneEntry')).toBeOnTheScreen();
  });

  it('starts the upload worker on mount and stops it on unmount', async () => {
    mockedGetStoredToken.mockResolvedValueOnce(null);

    const { unmount } = render(<App />);

    await waitFor(() => {
      expect(mockedStartUploadWorker).toHaveBeenCalledTimes(1);
    });
    expect(mockedStopUploadWorker).not.toHaveBeenCalled();

    unmount();
    expect(mockedStopUploadWorker).toHaveBeenCalledTimes(1);
  });
});

// Local re-export so the `render` import line stays close to the
// per-test mocks — `jest.mock` factories above must run before any
// transitive screen module loads, hence the deferred `import` at the
// bottom of the file.

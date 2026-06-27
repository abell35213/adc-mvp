# Driver App Dependency Risk Register

The driver app currently rides Expo SDK 54 and Jest/React Native tooling that bring in several transitive audit findings. The items below were reviewed on 2026-06-27 after adding a real `typecheck` script. Safe non-breaking fixes should be applied when available; major-SDK jumps remain follow-up work.

| Package | Severity | Dependency path | Exposure | Mitigation | Follow-up owner / action |
| --- | --- | --- | --- | --- | --- |
| `shell-quote` | Critical | `expo -> @expo/cli -> shell-quote` | Dev/build-time | No known runtime path in the shipped mobile app; limit CI/dev shell input sources and upgrade with the next Expo SDK refresh. | Mobile owner: upgrade Expo SDK and re-run `npm audit --audit-level=high`. |
| `form-data` | High | `jest-expo` / test tooling transitive chain | Dev/test-time | Keep untrusted filenames out of local test helpers; no production backend service consumes this package in the driver app runtime. | Mobile owner: accept temporarily, clear on next safe dependency refresh. |
| `undici` | High | `expo` tooling transitive dependency | Primarily dev/build-time | Not used directly by app business logic; keep Expo CLI updated within the current SDK line where possible. | Mobile owner: clear during next Expo SDK upgrade. |
| `ws` | High | `expo`, `react-native`, `jsdom` transitive dependencies | Dev/build-time with limited simulator exposure | Keep simulator/dev-server access restricted to trusted environments. | Mobile owner: clear during next Expo SDK upgrade. |
| `postcss` | Moderate | `expo -> @expo/config` toolchain | Dev/build-time | No direct mobile runtime use; track with Expo upgrades. | Mobile owner: revisit after SDK upgrade. |
| `js-yaml` | Moderate | Jest / Expo tooling | Dev/test-time | Do not feed untrusted YAML into test tooling. | Mobile owner: revisit after Jest/Expo dependency refresh. |
| `uuid` | Moderate | Expo config plugin toolchain | Dev/build-time | No direct app runtime usage from the vulnerable path. | Mobile owner: revisit after Expo upgrade. |

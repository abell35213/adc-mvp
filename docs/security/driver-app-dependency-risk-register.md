# Driver App Dependency Risk Register

The driver app currently rides Expo SDK 54 and Jest/React Native tooling that bring in several transitive audit findings. The items below were reviewed on 2026-06-27 after adding a real `typecheck` script, restoring the missing `react-native-worklets` peer dependency required by `react-native-reanimated`, and rerunning `npm audit --audit-level=high`. No high or critical findings remain; the unresolved items below are moderate-only and tied to the current Expo/Jest toolchain.

| Package | Severity | Dependency path | Exposure | Mitigation | Follow-up owner / action |
| --- | --- | --- | --- | --- | --- |
| `postcss` | Moderate | `expo -> @expo/config` toolchain | Dev/build-time | No direct mobile runtime use; track with Expo upgrades. | Mobile owner: revisit after SDK upgrade. |
| `js-yaml` | Moderate | Jest / Expo tooling | Dev/test-time | Do not feed untrusted YAML into test tooling. | Mobile owner: revisit after Jest/Expo dependency refresh. |
| `uuid` | Moderate | Expo config plugin toolchain | Dev/build-time | No direct app runtime usage from the vulnerable path. | Mobile owner: revisit after Expo upgrade. |

# Android preview build

The preview is a standalone app with bundled JavaScript. It does not require Metro once installed. It still needs a running QuantLens backend.

## GitHub Actions route

The manual `Android preview APK` workflow builds without an Expo account:

1. Publish the reviewed changes, including `.github/workflows/android-preview.yml`, to the repository's default branch.
2. Open GitHub Actions → Android preview APK → Run workflow.
3. Leave the optional API URL empty to configure the address inside the installed app.
4. Download the `quantlens-preview-apk` artifact after a successful run, unzip it, and install the APK.

The workflow generates Android files through Expo and builds an internal release APK for ARM64 phones and x86-64 emulators. Its generated debug signing key is for a classroom/internal demo; use proper release credentials for store distribution. Artifacts expire after 14 days.

## Expo Build route

With Node 24 active, sign into your own Expo account from the terminal and build:

```bash
cd mobile
npx eas-cli@latest login
npx eas-cli@latest build --platform android --profile preview
```

The first build may require linking the app to an Expo project and configuring signing credentials. Account sign-in is performed by the owner; do not put Expo passwords or tokens in the repository. Expo service availability and quotas apply. A local EAS build additionally requires an Android SDK/NDK and a compatible Java toolchain.

## Connect the installed app

On the laptop, run:

```bash
python3 scripts/dev.py --postgres
```

On the phone, open QuantLens Preview → Server connection. Enter `http://LAPTOP_LAN_IP:8000`, select Test connection, then Save connection. The phone and laptop must be on the same Wi-Fi and the backend port must be reachable. Use the laptop's LAN address; the phone's localhost points to the phone. The default browser preview and an explicitly configured API URL still work during development.

Changing servers clears the local account session before any account credentials can be sent to the new address. Data remains on its original server. Connection probes send no account tokens or cookies and require a ready QuantLens health response.

## Variants and transport

- Development: package suffix `.development`, local HTTP allowed, development client supported.
- Preview: package suffix `.preview`, bundled app, local HTTP allowed.
- Production: original package ID, HTTPS required in the app and cleartext disabled in generated Android configuration.

`APP_VARIANT` and `EXPO_PUBLIC_APP_VARIANT` must agree. EAS profiles and the APK workflow set both. Preview/production native settings are checked using Expo introspection; app URL checks also reject public cleartext URLs, embedded credentials, paths and query strings.

For local native generation, use:

```bash
APP_VARIANT=preview EXPO_PUBLIC_APP_VARIANT=preview npx expo prebuild --platform android --no-install
```

Generated `android/` and `ios/` directories remain ignored. Edit app configuration/plugins rather than generated native files.

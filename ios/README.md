# Axon Remote — iOS app

A native SwiftUI app that mirrors the dashboard. iPhone + iPad, dark mode
only, single screen with all the actions.

It speaks to the same relay as the web dashboard and the Siri Shortcuts.
No middle-layer, no SDK.

## What's in here

```
ios/
├── project.yml                 # XcodeGen spec (one-line project generation)
├── AxonRemote/
│   ├── AxonRemoteApp.swift     # @main entry, root view switch
│   ├── Theme.swift             # colors + .card() modifier
│   ├── Models.swift            # wire-format Codable types + AnyCodable
│   ├── Relay.swift             # SessionStore (@AppStorage) + RelayClient (URLSession)
│   ├── Info.plist              # ATS, dark mode, orientations
│   ├── Assets.xcassets/        # AppIcon + AccentColor
│   └── Views/
│       ├── LoginView.swift
│       ├── DashboardView.swift
│       ├── StatusHeaderView.swift
│       ├── PowerGridView.swift
│       ├── AppsGridView.swift
│       ├── ActivityListView.swift
│       └── ToastView.swift
```

## Setup option A — XcodeGen (recommended)

```bash
brew install xcodegen          # one-time
cd ios
xcodegen generate
open AxonRemote.xcodeproj
```

`project.yml` declares everything: bundle id `com.axon.remote`, iOS 16+,
universal device family. Tweak as needed.

## Setup option B — Manual Xcode project (no XcodeGen)

1. In Xcode: **File → New → Project → iOS → App**.
   - Product Name: `AxonRemote`
   - Interface: **SwiftUI**
   - Language: **Swift**
   - Storage: None
   - Save it as `c:/Testing/Test/ios/AxonRemote-tmp` (any temp folder is fine).
2. **Delete** Xcode's auto-generated `ContentView.swift` and `AxonRemoteApp.swift`.
3. Drag this folder's `AxonRemote/AxonRemoteApp.swift`, `Theme.swift`,
   `Models.swift`, `Relay.swift`, and the entire `Views/` folder into the
   project (tick **Copy items if needed** unchecked, **Create groups**).
4. In **Project → Targets → AxonRemote → Build Settings**:
   - `INFOPLIST_FILE` → set to `AxonRemote/Info.plist` (use the one in this repo).
5. Replace the auto-generated `Assets.xcassets` with the one from this folder
   (drag-replace).
6. Set **Deployment Target** to iOS 16.0.
7. Build & run.

## Configuring on the device

On first launch you'll see a sign-in screen:

- **Relay URL** — the public Railway URL of your relay
  (e.g. `https://axon-relay-production.up.railway.app`)
- **Bearer token** — the same `USER_API_KEY` you set on the relay

Both are stored in `UserDefaults` via `@AppStorage`. Sign out clears them.

## Why a native app instead of "just Siri Shortcuts"?

Siri Shortcuts are perfect for one-shot voice commands ("hey Siri, lock my
PC"). They are not great at:

- showing live status (online/offline, CPU, idle time)
- showing a scrollable activity log
- a fast launcher with a grid of apps
- providing immediate feedback ("agent_offline", "rate_limited", etc.)

This app handles those. It deliberately does **not** replace Siri Shortcuts —
both should coexist, hitting the same `/v1/cmd` endpoint with the same
bearer token.

## What's missing (and why)

- **No Apple Push Notifications.** That requires a developer cert + an
  APNs server in the relay. Phase 3 work.
- **No Keychain storage.** `@AppStorage` writes to `UserDefaults`, which is
  good enough for a personal app. Move to Keychain when you stop being the
  only user.
- **No live status over WebSocket.** The app polls every 4 s, which is
  fine for human use and keeps the iOS code tiny. Adding a WSS client is
  ~50 LoC if you ever care.

# ConnectOnion Studio — macOS app

A thin native shell: a `WKWebView` showing the same web UI (`co_studio/`), in a window with a
hidden title bar so the traffic-light buttons sit over the content — the look pywebview couldn't do.
The Swift shell talks to the studio server over `http://127.0.0.1`; it does **not** import the Python package.

**Status:** the Xcode project is set up and **builds clean** (verified with `xcodebuild`). Sources live
in `ConnectOnionStudio/ConnectOnionStudio/`:
- `ConnectOnionStudioApp.swift` — `@main` App + `ContentView`; `.windowStyle(.hiddenTitleBar)`
- `WebView.swift` — `WKWebView` wrapper
- `StudioServer.swift` — launches `co-studio` as a child process, waits for it, hands over the URL

## Run it (dev)

1. **Signing & Capabilities → remove "App Sandbox"** (dev launches a subprocess + hits localhost;
   the sandbox blocks both).
2. Point the shell at your local server — **Product → Scheme → Edit Scheme → Run → Arguments →
   Environment Variables**, add `CO_STUDIO_BIN` = `/absolute/path/to/connectonion-studio/.venv/bin/co-studio`
   (or leave it unset if `co-studio` is on your PATH).
3. **⌘R.** The app launches the server, waits until it answers, then shows the studio in a
   hidden-title-bar window.

## Build from the command line

The machine's `xcode-select` points at Command Line Tools, so pass Xcode explicitly:

```bash
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer xcodebuild \
  -project macos/ConnectOnionStudio/ConnectOnionStudio.xcodeproj \
  -scheme ConnectOnionStudio -configuration Debug -destination 'platform=macOS' \
  CODE_SIGNING_ALLOWED=NO build
```

## Ship it later (distribution — deferred)

Turning this into a downloadable `.dmg` needs a **self-contained server** inside the `.app`:

- ⚠️ The studio **spawns Python agent subprocesses** (`sys.executable …`), so a plain PyInstaller
  freeze breaks agent launch — the frozen binary isn't a Python interpreter. Options: bundle a
  relocatable Python (python-build-standalone) + the package, or a PyInstaller build that re-invokes
  itself to run the runner. **Tackle this as its own step.**
- Add entitlements (`com.apple.security.network.client`), code-sign + notarize, package a `.dmg`,
  attach it to a GitHub Release.
- Give `co-studio` a `--port` flag so the app can use a free port (it currently binds 9900 fixed).

import AppKit
import SwiftUI

@main
struct ConnectOnionStudioApp: App {
    // The delegate owns app-quit teardown and single-instance enforcement — things SwiftUI's view
    // lifecycle (onDisappear) can't do reliably.
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    // Same instance the delegate tears down on quit.
    @StateObject private var server = StudioServer.shared

    var body: some Scene {
        WindowGroup {
            ContentView(server: server)
                .frame(minWidth: 1160, minHeight: 800)
        }
        // The whole point of going native: hide the title bar so the red/yellow/green buttons
        // float over the content (top-left) — no grey bar, no pywebview private-API hacks.
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentSize)
        .commands {
            CommandGroup(replacing: .newItem) {}   // no "New Window" — this is a single-window app
        }
    }
}

/// App-quit teardown + single-instance guard. NSApplicationDelegate callbacks run on the main thread.
final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        enforceSingleInstance()
        // Kick off Sparkle's background update checks. The updater is loopback-independent; it reads
        // SUFeedURL/SUPublicEDKey from Info.plist and drives the web UI's banner via WebUpdater.
        MainActor.assumeIsolated { WebUpdater.shared.start() }
    }

    // Closing the (single) window quits the app, which routes through applicationWillTerminate below.
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    // The reliable "app is quitting" hook — unlike SwiftUI's onDisappear. Kill the server child here
    // so we never leak a headless co-studio (and, via --kill-agents-on-exit, its agent subprocesses).
    func applicationWillTerminate(_ notification: Notification) {
        MainActor.assumeIsolated { StudioServer.shared.shutdownForQuit() }
    }

    /// Two live supervisors would double-manage the shared ~/.co-studio registry + pidfiles and could
    /// cross-adopt each other's orphan agents. If another copy is already running, focus it and bow out.
    private func enforceSingleInstance() {
        let me = NSRunningApplication.current
        guard let bundleID = me.bundleIdentifier else { return }
        let others = NSRunningApplication.runningApplications(withBundleIdentifier: bundleID)
            .filter { $0.processIdentifier != me.processIdentifier && !$0.isTerminated }
        guard let existing = others.first else { return }
#if DEBUG
        // Dev: the newest build wins so ⌘R always runs current code — terminate the stale copy and
        // take over, instead of bowing to it and leaving you staring at yesterday's build.
        existing.terminate()
#else
        // Release: a second launch just focuses the running app — never a second server double-managing
        // the shared ~/.co-studio registry.
        _ = existing.activate()
        NSApp.terminate(nil)
#endif
    }
}

struct ContentView: View {
    @ObservedObject var server: StudioServer
    @State private var appearance = StudioAppearance.load()

    var body: some View {
        ZStack(alignment: .top) {
            phaseContent

            // WKWebView swallows title-bar drags, so the reserved top strip (CSS --titlebar-h: 30px,
            // the "native-drag zone") gets a real drag region. Inset from BOTH top corners so it never
            // covers the traffic lights (top-left) or the settings gear (.firstrun-gear, top-right).
            WindowDragArea()
                .frame(height: DesktopChrome.titlebarHeight)
                .frame(maxWidth: .infinity)
                .padding(.leading, DesktopChrome.leadingInset)
                .padding(.trailing, DesktopChrome.trailingInset)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .ignoresSafeArea()          // web content extends under the (hidden) title bar
        .background(WindowAccessor { window in
            // Lets the spinner / error phases drag from anywhere; the strip above covers the WebView.
            window.isMovableByWindowBackground = true
            // Paper (not system white) so the launch seam never flashes before the web UI paints.
            window.backgroundColor = appearance.canvasNSColor
        })
        .onAppear { server.start() }
        // Teardown is applicationWillTerminate's job (see AppDelegate) — NOT onDisappear, which is
        // tied to view teardown and would kill the server on transient view churn.
    }

    @ViewBuilder private var phaseContent: some View {
        switch server.phase {
        case .running(let url):
            RunningView(url: url, appearance: $appearance).id(url)   // fresh cover state per launch (e.g. after Retry)
        case .failed(let message):
            LaunchErrorView(message: message,
                            onRetry: server.retry,
                            onCopyLogs: server.copyLogs)
        case .starting:
            StartingView(appearance: appearance)
        }
    }
}

/// The paper "Starting…" cover — shared by the launch phase AND the hold-over during page load, so the
/// spinner is visually continuous from launch straight into the web UI's own splash.
private struct StartingView: View {
    let appearance: StudioAppearance

    var body: some View {
        VStack(spacing: 12) {
            ProgressView()
                .tint(Color(nsColor: appearance.accentNSColor))
            Text("Starting ConnectOnion Studio…")
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: appearance.canvasNSColor))   // paper, matches the web UI's splash
    }
}

/// Running phase: the web UI loads UNDER an opaque paper cover. We only fade the cover once the page
/// has painted (WebView `onReady` / didFinish), so the WKWebView's white loading document never shows
/// in the seam between the spinner and the app's own splash animation.
private struct RunningView: View {
    let url: URL
    @Binding var appearance: StudioAppearance
    @State private var pageReady = false

    var body: some View {
        ZStack {
            WebView(
                url: url,
                appearance: appearance,
                onReady: { pageReady = true },
                onAppearanceChange: { appearance = $0 }
            )
            StartingView(appearance: appearance)
                .opacity(pageReady ? 0 : 1)
                .allowsHitTesting(!pageReady)
        }
        .animation(.easeOut(duration: 0.25), value: pageReady)
        .task {
            // Safety net: server readiness was already confirmed, so the page WILL load — but never
            // strand the cover if didFinish is somehow missed.
            try? await Task.sleep(nanoseconds: 4_000_000_000)
            pageReady = true
        }
    }
}

/// Shown when the server never comes up — replaces the old infinite spinner with a way out.
struct LaunchErrorView: View {
    let message: String
    let onRetry: () -> Void
    let onCopyLogs: () -> Void
    @State private var copied = false

    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 34))
                .foregroundStyle(.secondary)
            Text("ConnectOnion Studio couldn't start")
                .font(.headline)
            Text(message)
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 420)
            HStack(spacing: 12) {
                Button("Retry", action: onRetry)
                    .keyboardShortcut(.defaultAction)
                Button(copied ? "Copied" : "Copy logs") {
                    onCopyLogs()
                    copied = true
                }
            }
            .padding(.top, 4)
        }
        .padding(40)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

// MARK: - Native window chrome

enum StudioAppearance: String {
    case warm
    case lavender

    /// Read the same ~/.co-studio/config.json setting used by the backend. Unlike web storage, this
    /// path is stable even though the native shell deliberately chooses a new free port each launch.
    static func load() -> StudioAppearance {
        let configURL = FileManager.default.homeDirectoryForCurrentUser
            .appendingPathComponent(".co-studio/config.json")
        guard let data = try? Data(contentsOf: configURL),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let raw = object["appearance"] as? String,
              let appearance = StudioAppearance(rawValue: raw) else { return .warm }
        return appearance
    }

    var canvasNSColor: NSColor {
        switch self {
        case .warm:
            return NSColor(srgbRed: 0xF0 / 255.0, green: 0xEE / 255.0, blue: 0xE6 / 255.0, alpha: 1)   // #F0EEE6
        case .lavender:
            return NSColor(srgbRed: 0xED / 255.0, green: 0xEC / 255.0, blue: 0xF6 / 255.0, alpha: 1)   // #EDECF6
        }
    }

    var accentNSColor: NSColor {
        switch self {
        case .warm:
            return NSColor(srgbRed: 0x9A / 255.0, green: 0x5B / 255.0, blue: 0x3A / 255.0, alpha: 1)   // #9A5B3A
        case .lavender:
            return NSColor(srgbRed: 0x6E / 255.0, green: 0x56 / 255.0, blue: 0xF2 / 255.0, alpha: 1)   // #6E56F2
        }
    }
}

enum DesktopChrome {
    /// Height of the reserved top strip; mirrors CSS `--titlebar-h: 30px` (html.desktop, app.css).
    static let titlebarHeight: CGFloat = 30
    /// Clear the macOS traffic lights (top-left, ~78pt).
    static let leadingInset: CGFloat = 80
    /// Clear the settings gear (.firstrun-gear: top:20 right:22 width:38 → ~60pt from the right edge).
    static let trailingInset: CGFloat = 72

}

/// Grabs the hosting NSWindow once it exists and applies native-shell tweaks.
struct WindowAccessor: NSViewRepresentable {
    let configure: (NSWindow) -> Void

    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        apply(to: view, retries: 30)   // the view has no window yet at makeNSView time
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        DispatchQueue.main.async { if let window = nsView.window { configure(window) } }
    }

    /// Poll a few frames until the view is attached to its NSWindow, then configure it once.
    private func apply(to view: NSView, retries: Int) {
        DispatchQueue.main.async {
            if let window = view.window { configure(window) }
            else if retries > 0 { apply(to: view, retries: retries - 1) }
        }
    }
}

/// A transparent strip that initiates a native window drag — WKWebView won't pass drags to the window,
/// so we overlay this over the reserved (empty) top strip. It sits under the traffic-light buttons in
/// z-order (those live in the window frame, above the content view), so it never blocks them.
struct WindowDragArea: NSViewRepresentable {
    func makeNSView(context: Context) -> NSView { DraggableView() }
    func updateNSView(_ nsView: NSView, context: Context) {}
}

private final class DraggableView: NSView {
    override var mouseDownCanMoveWindow: Bool { true }

    // SwiftUI's hosting view swallows `mouseDownCanMoveWindow`, so the declarative hint alone doesn't
    // move the window. Start the drag explicitly from the mouse-down event — this is what actually
    // makes the reserved top strip draggable.
    override func mouseDown(with event: NSEvent) {
        window?.performDrag(with: event)
    }
}

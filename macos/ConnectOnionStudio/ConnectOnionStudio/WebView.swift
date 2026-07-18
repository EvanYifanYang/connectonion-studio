import AppKit
import SwiftUI
import WebKit

/// A WKWebView that fills the window and shows the studio's existing web UI.
struct WebView: NSViewRepresentable {
    let url: URL
    var onReady: () -> Void = {}

    func makeCoordinator() -> Coordinator { Coordinator(onReady: onReady) }

    func makeNSView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        // Same-origin loopback app; JS on. ATS permits the numeric loopback 127.0.0.1 without an
        // exception (only the "localhost" hostname would need NSAllowsLocalNetworking — see README).
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = context.coordinator
        webView.uiDelegate = context.coordinator
        // Paper base (CSS --canvas) so the load-in moment shows brand color, not a white flash — matches
        // the window + spinner. Public API (macOS 12+), replaces the old private `drawsBackground` KVC.
        webView.underPageBackgroundColor = DesktopChrome.canvasNSColor
        webView.load(URLRequest(url: url))
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        context.coordinator.onReady = onReady   // keep the callback fresh across view updates
        if webView.url != url {
            webView.load(URLRequest(url: url))
        }
    }

    /// Keeps in-window navigation on our loopback origin and routes everything else to the system
    /// browser. WKWebView drops `target=_blank` / `window.open` by default, so those links (GitHub,
    /// "Powered by OpenOnion", onboarding docs) are dead without this handler.
    final class Coordinator: NSObject, WKNavigationDelegate, WKUIDelegate {
        /// Fired once the page finishes loading (so it has painted its paper background) — the cue to
        /// fade the paper cover, so the WKWebView's white loading document is never seen.
        var onReady: () -> Void
        init(onReady: @escaping () -> Void) { self.onReady = onReady }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            onReady()
        }

        func webView(_ webView: WKWebView,
                     decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let url = navigationAction.request.url else { decisionHandler(.allow); return }
            if Coordinator.staysInApp(url) {
                decisionHandler(.allow)
            } else {
                Coordinator.openExternally(url)
                decisionHandler(.cancel)
            }
        }

        func webView(_ webView: WKWebView,
                     createWebViewWith configuration: WKWebViewConfiguration,
                     for navigationAction: WKNavigationAction,
                     windowFeatures: WKWindowFeatures) -> WKWebView? {
            if let url = navigationAction.request.url {
                if Coordinator.isLoopback(url) {
                    webView.load(navigationAction.request)   // an internal target=_blank stays in-window
                } else {
                    Coordinator.openExternally(url)          // external → system browser
                }
            }
            return nil   // never spawn a second WKWebView window
        }

        private static func staysInApp(_ url: URL) -> Bool {
            switch url.scheme?.lowercased() {
            case "http", "https", "ws", "wss": return isLoopback(url)
            case "about", "blob", "data":      return true   // WebKit internals
            default:                           return false
            }
        }

        private static func isLoopback(_ url: URL) -> Bool {
            switch url.host {
            case "127.0.0.1", "localhost", "::1": return true
            default:                              return false
            }
        }

        private static func openExternally(_ url: URL) {
            switch url.scheme?.lowercased() {
            case "about", "blob", "data", .none: return   // nothing sensible to hand off
            default: NSWorkspace.shared.open(url)
            }
        }
    }
}

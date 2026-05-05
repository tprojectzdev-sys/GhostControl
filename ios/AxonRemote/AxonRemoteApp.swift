import SwiftUI

@main
struct AxonRemoteApp: App {
    @StateObject private var session = SessionStore()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(session)
                .preferredColorScheme(.dark)
                .tint(Theme.accent)
        }
    }
}

struct RootView: View {
    @EnvironmentObject private var session: SessionStore

    var body: some View {
        Group {
            if session.isAuthenticated {
                DashboardView()
            } else {
                LoginView()
            }
        }
        .background(Theme.background.ignoresSafeArea())
    }
}

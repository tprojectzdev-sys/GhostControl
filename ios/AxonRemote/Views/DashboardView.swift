import SwiftUI

@MainActor
final class DashboardModel: ObservableObject {
    @Published var status: RelayStatus?
    @Published var statusError: String?
    @Published var audit: [AuditEvent] = []
    @Published var isRefreshing = false
    @Published var pendingCommand: CommandName?
    @Published var toast: Toast?

    private var statusTimer: Timer?
    private var auditTimer: Timer?

    func start(client: RelayClient) {
        statusTimer?.invalidate()
        auditTimer?.invalidate()
        Task { await self.refreshStatus(client: client) }
        Task { await self.refreshAudit(client: client) }
        statusTimer = Timer.scheduledTimer(withTimeInterval: 4, repeats: true) { _ in
            Task { await self.refreshStatus(client: client) }
        }
        auditTimer = Timer.scheduledTimer(withTimeInterval: 6, repeats: true) { _ in
            Task { await self.refreshAudit(client: client) }
        }
    }

    func stop() {
        statusTimer?.invalidate(); statusTimer = nil
        auditTimer?.invalidate();  auditTimer = nil
    }

    func refreshStatus(client: RelayClient) async {
        do {
            let s = try await client.status()
            await MainActor.run {
                self.status = s
                self.statusError = nil
            }
        } catch {
            await MainActor.run { self.statusError = error.localizedDescription }
        }
    }

    func refreshAudit(client: RelayClient) async {
        do {
            let evs = try await client.audit(limit: 50).reversed()
            await MainActor.run { self.audit = Array(evs) }
        } catch {
            // Audit failures are silent; the status pill already reflects auth issues.
        }
    }

    func send(_ name: CommandName, args: [String: Any] = [:], label: String? = nil, client: RelayClient) async {
        await MainActor.run { pendingCommand = name }
        defer { Task { @MainActor in pendingCommand = nil } }
        do {
            let res = try await client.send(name, args: args)
            await present(name: name, response: res, label: label)
        } catch RelayError.unauthorized {
            await MainActor.run { toast = .err("Token rejected") }
        } catch {
            await MainActor.run { toast = .err("\(name.rawValue): \(error.localizedDescription)") }
        }
        await refreshStatus(client: client)
        await refreshAudit(client: client)
    }

    private func present(name: CommandName, response: CommandResponse, label: String?) async {
        let nice = label.map { "\(name.rawValue) (\($0))" } ?? name.rawValue
        switch response.status {
        case "ok":
            await MainActor.run { toast = .ok("\(nice) — ok") }
        case "agent_offline":
            await MainActor.run { toast = .warn("\(nice) — agent offline") }
        case "timeout":
            await MainActor.run { toast = .warn("\(nice) — timeout") }
        case "rate_limited":
            await MainActor.run { toast = .warn("\(nice) — rate limited") }
        default:
            let msg = response.message ?? response.code ?? response.status
            await MainActor.run { toast = .err("\(nice) — \(msg)") }
        }
    }
}

struct DashboardView: View {
    @EnvironmentObject private var session: SessionStore
    @StateObject private var model = DashboardModel()
    @State private var refreshTrigger = UUID()

    private var pcOnline: Bool { model.status?.pc != nil }
    private var bridgeOnline: Bool { model.status?.bridge != nil }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                StatusHeaderView(status: model.status,
                                 statusError: model.statusError,
                                 onSignOut: { session.signOut() })
                PowerGridView(
                    pcOnline: pcOnline,
                    bridgeOnline: bridgeOnline,
                    pending: model.pendingCommand,
                    onTap: { cmd in
                        Task { await model.send(cmd, client: session.client) }
                    }
                )
                AppsGridView(
                    pcOnline: pcOnline,
                    pending: model.pendingCommand,
                    onAppTap: { alias in
                        Task { await model.send(.appOpen, args: ["target": alias], label: alias, client: session.client) }
                    },
                    onGroupTap: { alias in
                        Task { await model.send(.groupRun, args: ["target": alias], label: alias, client: session.client) }
                    },
                    onURLSubmit: { url in
                        Task { await model.send(.urlOpen, args: ["url": url], label: url, client: session.client) }
                    }
                )
                ActivityListView(events: model.audit)
            }
            .padding(16)
        }
        .background(Theme.background.ignoresSafeArea())
        .refreshable {
            await model.refreshStatus(client: session.client)
            await model.refreshAudit(client: session.client)
        }
        .onAppear { model.start(client: session.client) }
        .onDisappear { model.stop() }
        .overlay(alignment: .bottom) {
            if let t = model.toast {
                ToastView(toast: t) { model.toast = nil }
                    .padding(16)
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .animation(.easeInOut(duration: 0.2), value: model.toast)
    }
}

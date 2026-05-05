import SwiftUI

struct LoginView: View {
    @EnvironmentObject private var session: SessionStore
    @State private var baseUrl: String = "https://your-relay.up.railway.app"
    @State private var token: String = ""
    @State private var busy = false
    @State private var error: String?

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            VStack(alignment: .leading, spacing: 18) {
                HStack(spacing: 12) {
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .fill(Theme.accentSoft)
                        .frame(width: 44, height: 44)
                        .overlay(
                            Text("A")
                                .font(.title2.weight(.bold))
                                .foregroundStyle(Theme.accent)
                        )
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Axon Remote")
                            .font(.title3.weight(.semibold))
                            .foregroundStyle(Theme.textPrimary)
                        Text("Sign in with your relay credentials")
                            .font(.caption)
                            .foregroundStyle(Theme.textSecondary)
                    }
                }
                .padding(.bottom, 6)

                VStack(alignment: .leading, spacing: 6) {
                    Text("Relay URL").sectionTitleStyle()
                    TextField("https://your-relay.up.railway.app", text: $baseUrl)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                        .padding(.horizontal, 14).padding(.vertical, 12)
                        .background(
                            RoundedRectangle(cornerRadius: 14, style: .continuous)
                                .fill(Theme.surfaceHi)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                                        .stroke(.white.opacity(0.06), lineWidth: 1)
                                )
                        )
                        .foregroundStyle(Theme.textPrimary)
                }

                VStack(alignment: .leading, spacing: 6) {
                    Text("Bearer token").sectionTitleStyle()
                    SecureField("USER_API_KEY", text: $token)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .padding(.horizontal, 14).padding(.vertical, 12)
                        .background(
                            RoundedRectangle(cornerRadius: 14, style: .continuous)
                                .fill(Theme.surfaceHi)
                                .overlay(
                                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                                        .stroke(.white.opacity(0.06), lineWidth: 1)
                                )
                        )
                        .font(.system(.body, design: .monospaced))
                        .foregroundStyle(Theme.textPrimary)
                }

                if let error = error {
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(Theme.err)
                        .padding(10)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .fill(Theme.err.opacity(0.10))
                                .overlay(
                                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                                        .stroke(Theme.err.opacity(0.25), lineWidth: 1)
                                )
                        )
                }

                Button(action: signIn) {
                    HStack {
                        if busy { ProgressView().controlSize(.small) }
                        Text("Sign in").fontWeight(.semibold)
                        Spacer()
                        Image(systemName: "arrow.right")
                    }
                    .foregroundStyle(Theme.accent)
                    .padding(.horizontal, 16).padding(.vertical, 14)
                    .frame(maxWidth: .infinity)
                    .background(
                        RoundedRectangle(cornerRadius: 14, style: .continuous)
                            .fill(Theme.accentSoft)
                    )
                }
                .disabled(busy)
                .padding(.top, 6)

                Label {
                    Text("Token is stored only on this device. HTTPS only.")
                        .font(.caption2).foregroundStyle(Theme.textMuted)
                } icon: {
                    Image(systemName: "lock.shield").foregroundStyle(Theme.textMuted)
                }

                Spacer()
            }
            .padding(24)
            .card(elevated: true)
            .padding(20)
        }
    }

    private func signIn() {
        let url = baseUrl.trimmingCharacters(in: .whitespacesAndNewlines)
        let tok = token.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !url.isEmpty, !tok.isEmpty else { error = "Both fields are required."; return }
        guard URL(string: url) != nil else { error = "Relay URL is not a valid URL."; return }

        busy = true
        error = nil
        Task {
            defer { Task { @MainActor in busy = false } }
            let probe = RelayClient(baseUrl: url, token: tok)
            do {
                let healthy = try await probe.probe()
                guard healthy else { await MainActor.run { error = "Could not reach /healthz." }; return }
                _ = try await probe.status()
                await MainActor.run { session.signIn(baseUrl: url, token: tok) }
            } catch RelayError.unauthorized {
                await MainActor.run { error = "Token rejected by the relay." }
            } catch {
                await MainActor.run { self.error = error.localizedDescription }
            }
        }
    }
}

import SwiftUI

struct PowerGridView: View {
    let pcOnline: Bool
    let bridgeOnline: Bool
    let pending: CommandName?
    let onTap: (CommandName) -> Void

    @State private var pendingConfirm: CommandName?
    @State private var showingConfirm = false

    private struct Item: Identifiable {
        let id = UUID()
        let cmd: CommandName
        let label: String
        let symbol: String
        let needsBridge: Bool
        let needsPC: Bool
    }

    private let items: [Item] = [
        Item(cmd: .powerWake,     label: "Wake",     symbol: "bolt.fill",                needsBridge: true,  needsPC: false),
        Item(cmd: .powerLock,     label: "Lock",     symbol: "lock.fill",                needsBridge: false, needsPC: true),
        Item(cmd: .powerSleep,    label: "Sleep",    symbol: "moon.fill",                needsBridge: false, needsPC: true),
        Item(cmd: .powerRestart,  label: "Restart",  symbol: "arrow.clockwise",          needsBridge: false, needsPC: true),
        Item(cmd: .powerShutdown, label: "Shutdown", symbol: "power",                    needsBridge: false, needsPC: true),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Text("Power").sectionTitleStyle()
                Spacer()
                Text("tap to send").font(.caption2).foregroundStyle(Theme.textMuted)
            }
            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: 10),
                GridItem(.flexible(), spacing: 10),
                GridItem(.flexible(), spacing: 10),
            ], spacing: 10) {
                ForEach(items) { item in
                    let disabled =
                        pending != nil ||
                        (item.needsBridge && !bridgeOnline) ||
                        (item.needsPC && !pcOnline)
                    Button {
                        if item.cmd.isDestructive {
                            pendingConfirm = item.cmd
                            showingConfirm = true
                        } else {
                            onTap(item.cmd)
                        }
                    } label: {
                        PowerTile(
                            label: item.label,
                            cmd: item.cmd.rawValue,
                            symbol: item.symbol,
                            destructive: item.cmd.isDestructive,
                            sending: pending == item.cmd
                        )
                    }
                    .disabled(disabled)
                    .opacity(disabled ? 0.5 : 1)
                }
            }
        }
        .card()
        .alert(
            "Confirm \(pendingConfirm?.rawValue ?? "")?",
            isPresented: $showingConfirm,
            presenting: pendingConfirm
        ) { cmd in
            Button("Send", role: .destructive) { onTap(cmd) }
            Button("Cancel", role: .cancel) { }
        } message: { _ in
            Text("This will affect your PC immediately.")
        }
    }
}

private struct PowerTile: View {
    let label: String
    let cmd: String
    let symbol: String
    let destructive: Bool
    let sending: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(destructive ? Theme.err.opacity(0.12) : Theme.accentSoft)
                    .frame(width: 32, height: 32)
                Image(systemName: symbol)
                    .font(.body)
                    .foregroundStyle(destructive ? Theme.err : Theme.accent)
            }
            Spacer(minLength: 0)
            Text(label)
                .font(.subheadline.weight(.semibold))
                .foregroundStyle(Theme.textPrimary)
            Text(cmd)
                .font(.caption2.monospaced())
                .foregroundStyle(Theme.textMuted)
                .lineLimit(1)
        }
        .padding(12)
        .frame(height: 110, alignment: .topLeading)
        .frame(maxWidth: .infinity)
        .background(
            RoundedRectangle(cornerRadius: Theme.tileCorner, style: .continuous)
                .fill(Theme.surfaceHover.opacity(0.7))
        )
        .overlay(
            Group {
                if sending {
                    ZStack {
                        RoundedRectangle(cornerRadius: Theme.tileCorner, style: .continuous)
                            .fill(Theme.surfaceHi.opacity(0.7))
                        ProgressView().controlSize(.small)
                    }
                }
            }
        )
    }
}

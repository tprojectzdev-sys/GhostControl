import SwiftUI

struct StatusHeaderView: View {
    let status: RelayStatus?
    let statusError: String?
    let onSignOut: () -> Void

    private var anyOnline: Bool { status?.pc != nil || status?.bridge != nil }
    private var hostname: String { status?.pc?.status.hostname ?? status?.pc?.agent_id ?? "—" }

    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            HStack(alignment: .firstTextBaseline) {
                Text(timeString)
                    .font(.system(size: 40, weight: .semibold, design: .default))
                    .foregroundStyle(Theme.textPrimary)
                Spacer()
                Pill(text: anyOnline ? "ALL SYSTEMS NOMINAL" : "AGENT OFFLINE",
                     color: anyOnline ? Theme.ok : Theme.err)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text(greeting + ", \(hostname)")
                    .font(.subheadline)
                    .foregroundStyle(Theme.textSecondary)
                Text("Overview")
                    .font(.title3.weight(.semibold))
                    .foregroundStyle(Theme.textPrimary)
            }
            HStack(spacing: 12) {
                StatusRow(label: "PC Agent",
                          sub: status?.pc?.status.hostname ?? status?.pc?.agent_id ?? "—",
                          online: status?.pc != nil,
                          right: status?.pc.map { "\(formatUptime($0.uptime_seconds))" } ?? "offline")
                StatusRow(label: "WoL Bridge",
                          sub: status?.bridge?.status.hostname ?? status?.bridge?.agent_id ?? "—",
                          online: status?.bridge != nil,
                          right: status?.bridge.map { "\(formatUptime($0.uptime_seconds))" } ?? "offline")
            }

            HStack {
                if let err = statusError {
                    Text(err)
                        .font(.caption2)
                        .foregroundStyle(Theme.err)
                        .lineLimit(1)
                }
                Spacer()
                Button(action: onSignOut) {
                    Label("Sign out", systemImage: "rectangle.portrait.and.arrow.right")
                        .font(.caption.weight(.medium))
                        .foregroundStyle(Theme.textSecondary)
                }
            }
        }
        .card(elevated: true)
    }

    private var timeString: String {
        let f = DateFormatter()
        f.dateFormat = "h:mm a"
        return f.string(from: Date())
    }

    private var greeting: String {
        let h = Calendar.current.component(.hour, from: Date())
        switch h {
        case 0..<5:   return "Up late"
        case 5..<12:  return "Good morning"
        case 12..<17: return "Good afternoon"
        case 17..<22: return "Good evening"
        default:      return "Good night"
        }
    }
}

struct StatusRow: View {
    let label: String
    let sub: String
    let online: Bool
    let right: String

    var body: some View {
        HStack(spacing: 10) {
            Circle()
                .fill(online ? Theme.ok : Theme.err)
                .frame(width: 9, height: 9)
                .shadow(color: (online ? Theme.ok : Theme.err).opacity(0.4), radius: 4)
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.subheadline.weight(.medium))
                    .foregroundStyle(Theme.textPrimary)
                Text(sub)
                    .font(.caption2)
                    .foregroundStyle(Theme.textMuted)
                    .lineLimit(1)
            }
            Spacer()
            Text(right)
                .font(.caption.monospacedDigit())
                .foregroundStyle(Theme.textSecondary)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(
            RoundedRectangle(cornerRadius: Theme.tileCorner, style: .continuous)
                .fill(Theme.surfaceHover.opacity(0.6))
        )
    }
}

struct Pill: View {
    let text: String
    let color: Color
    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 6, height: 6)
            Text(text)
                .font(.caption2.weight(.semibold))
                .tracking(1)
        }
        .foregroundStyle(color)
        .padding(.horizontal, 10)
        .padding(.vertical, 5)
        .background(
            Capsule().fill(color.opacity(0.10))
        )
    }
}

func formatUptime(_ seconds: Int) -> String {
    if seconds < 60 { return "\(seconds)s" }
    if seconds < 3600 { return "\(seconds/60)m \(seconds%60)s" }
    if seconds < 86400 {
        let h = seconds / 3600
        let m = (seconds % 3600) / 60
        return "\(h)h \(m)m"
    }
    let d = seconds / 86400
    let h = (seconds % 86400) / 3600
    return "\(d)d \(h)h"
}

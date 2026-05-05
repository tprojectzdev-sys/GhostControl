import SwiftUI

struct ActivityListView: View {
    let events: [AuditEvent]

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "waveform.path.ecg")
                    .font(.caption)
                    .foregroundStyle(Theme.textSecondary)
                Text("Activity").sectionTitleStyle()
                Spacer()
                Text("last \(events.count)")
                    .font(.caption2)
                    .foregroundStyle(Theme.textMuted)
            }

            if events.isEmpty {
                Text("No activity yet.")
                    .font(.subheadline)
                    .foregroundStyle(Theme.textMuted)
                    .frame(maxWidth: .infinity, alignment: .center)
                    .padding(.vertical, 24)
            } else {
                LazyVStack(spacing: 0) {
                    ForEach(Array(events.enumerated()), id: \.offset) { idx, e in
                        if idx > 0 {
                            Divider().background(Color.white.opacity(0.04))
                        }
                        AuditRow(event: e)
                    }
                }
            }
        }
        .card()
    }
}

private struct AuditRow: View {
    let event: AuditEvent

    var body: some View {
        HStack(spacing: 10) {
            ZStack {
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(Color.white.opacity(0.03))
                    .frame(width: 28, height: 28)
                Image(systemName: symbol)
                    .font(.caption)
                    .foregroundStyle(tone)
            }
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.subheadline)
                    .foregroundStyle(Theme.textPrimary)
                    .lineLimit(1)
                if !subtitle.isEmpty {
                    Text(subtitle)
                        .font(.caption2)
                        .foregroundStyle(Theme.textMuted)
                        .lineLimit(1)
                }
            }
            Spacer()
            Text(relative)
                .font(.caption2.monospacedDigit())
                .foregroundStyle(Theme.textMuted)
        }
        .padding(.vertical, 10)
    }

    private var isCmd: Bool { event.kind == "cmd_in" }

    private var title: String {
        if isCmd {
            let target = (event.args?["target"]?.value as? String).map { " \($0)" } ?? ""
            let urlArg = (event.args?["url"]?.value as? String).map { " \($0)" } ?? ""
            return "\(event.cmd ?? "?")\(target)\(urlArg)"
        }
        switch event.kind {
        case "agent_connect":    return "\(event.role ?? "agent") connected"
        case "agent_disconnect": return "\(event.role ?? "agent") disconnected"
        default: return event.kind
        }
    }

    private var subtitle: String {
        if isCmd {
            let outcome = event.outcome ?? ""
            if let m = event.ack_message, !m.isEmpty { return "\(outcome) · \(m)" }
            return outcome
        }
        return event.os ?? event.hostname ?? event.agent_id ?? ""
    }

    private var symbol: String {
        if isCmd {
            switch event.outcome {
            case "ok": return "checkmark.circle.fill"
            case "agent_offline", "timeout": return "exclamationmark.triangle.fill"
            default: return "xmark.octagon.fill"
            }
        }
        return event.kind == "agent_connect" ? "antenna.radiowaves.left.and.right" : "antenna.radiowaves.left.and.right.slash"
    }

    private var tone: Color {
        if isCmd {
            switch event.outcome {
            case "ok": return Theme.ok
            case "agent_offline", "timeout": return Theme.warn
            default: return Theme.err
            }
        }
        return event.kind == "agent_connect" ? Theme.ok : Theme.textSecondary
    }

    private var relative: String {
        let secs = max(0, Int(Date().timeIntervalSince1970) - event.ts_ms / 1000)
        if secs < 60 { return "\(secs)s ago" }
        if secs < 3600 { return "\(secs/60)m ago" }
        if secs < 86400 { return "\(secs/3600)h ago" }
        return "\(secs/86400)d ago"
    }
}

import SwiftUI

struct Toast: Equatable {
    enum Level { case ok, warn, err }
    let level: Level
    let message: String

    static func ok(_ m: String)   -> Toast { .init(level: .ok,   message: m) }
    static func warn(_ m: String) -> Toast { .init(level: .warn, message: m) }
    static func err(_ m: String)  -> Toast { .init(level: .err,  message: m) }
}

struct ToastView: View {
    let toast: Toast
    let onDismiss: () -> Void

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: symbol)
                .foregroundStyle(color)
            Text(toast.message)
                .font(.subheadline)
                .foregroundStyle(Theme.textPrimary)
                .frame(maxWidth: .infinity, alignment: .leading)
            Button(action: onDismiss) {
                Image(systemName: "xmark")
                    .font(.caption)
                    .foregroundStyle(Theme.textSecondary)
            }
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(Theme.surfaceHi)
                .overlay(
                    RoundedRectangle(cornerRadius: 14, style: .continuous)
                        .stroke(color.opacity(0.35), lineWidth: 1)
                )
        )
        .shadow(color: .black.opacity(0.4), radius: 16, y: 6)
        .frame(maxWidth: 480)
        .task {
            try? await Task.sleep(nanoseconds: 4_500_000_000)
            onDismiss()
        }
    }

    private var symbol: String {
        switch toast.level {
        case .ok:   return "checkmark.circle.fill"
        case .warn: return "exclamationmark.triangle.fill"
        case .err:  return "xmark.octagon.fill"
        }
    }
    private var color: Color {
        switch toast.level {
        case .ok:   return Theme.ok
        case .warn: return Theme.warn
        case .err:  return Theme.err
        }
    }
}

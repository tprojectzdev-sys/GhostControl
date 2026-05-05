import SwiftUI

/// Visual language shared by the iOS app and the web dashboard.
/// Dark, low-contrast surfaces, single warm accent.
enum Theme {
    static let background      = Color(red: 0.027, green: 0.027, blue: 0.031)   // #070708
    static let surface         = Color(red: 0.063, green: 0.063, blue: 0.071)   // #101012
    static let surfaceHi       = Color(red: 0.082, green: 0.082, blue: 0.094)   // #15151a
    static let surfaceHover    = Color(red: 0.102, green: 0.102, blue: 0.118)   // #1a1a20

    static let textPrimary     = Color(red: 0.906, green: 0.906, blue: 0.925)   // #e7e7ec
    static let textSecondary   = Color(red: 0.547, green: 0.547, blue: 0.604)   // #8b8b9a
    static let textMuted       = Color(red: 0.357, green: 0.357, blue: 0.420)   // #5b5b6b

    static let accent          = Color(red: 0.961, green: 0.651, blue: 0.137)   // #f5a623
    static let accentSoft      = Color(red: 0.961, green: 0.651, blue: 0.137).opacity(0.18)
    static let ok              = Color(red: 0.239, green: 0.863, blue: 0.592)   // #3ddc97
    static let warn            = Color(red: 0.961, green: 0.776, blue: 0.259)   // #f5c542
    static let err             = Color(red: 0.937, green: 0.325, blue: 0.314)   // #ef5350

    static let cardCorner: CGFloat = 24
    static let tileCorner: CGFloat = 16
}

struct CardBackground: ViewModifier {
    var elevated: Bool = false
    func body(content: Content) -> some View {
        content
            .padding(20)
            .background(
                RoundedRectangle(cornerRadius: Theme.cardCorner, style: .continuous)
                    .fill(elevated ? Theme.surfaceHi : Theme.surface)
                    .overlay(
                        RoundedRectangle(cornerRadius: Theme.cardCorner, style: .continuous)
                            .strokeBorder(.white.opacity(0.04), lineWidth: 1)
                    )
            )
    }
}

extension View {
    func card(elevated: Bool = false) -> some View {
        self.modifier(CardBackground(elevated: elevated))
    }

    func sectionTitleStyle() -> some View {
        self
            .font(.caption.weight(.semibold))
            .tracking(2)
            .textCase(.uppercase)
            .foregroundStyle(Theme.textSecondary)
    }
}

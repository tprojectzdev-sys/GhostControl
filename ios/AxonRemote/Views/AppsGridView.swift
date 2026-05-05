import SwiftUI

struct AppsGridView: View {
    let pcOnline: Bool
    let pending: CommandName?
    let onAppTap: (String) -> Void
    let onGroupTap: (String) -> Void
    let onURLSubmit: (String) -> Void

    @AppStorage("axon.apps") private var appsCSV: String = "chrome,vscode,spotify,steam,discord,notepad"
    @AppStorage("axon.groups") private var groupsCSV: String = "work_morning,media_mode"
    @State private var tab: Tab = .apps
    @State private var url: String = ""
    @State private var editingAliases: Bool = false

    enum Tab: String, CaseIterable, Identifiable {
        case apps, groups, url
        var id: String { rawValue }
        var label: String { self == .url ? "URL" : rawValue.capitalized }
    }

    private var apps: [String] {
        appsCSV.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
    }
    private var groups: [String] {
        groupsCSV.split(separator: ",").map { $0.trimmingCharacters(in: .whitespaces) }.filter { !$0.isEmpty }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Text("Launcher").sectionTitleStyle()
                Spacer()
                Picker("", selection: $tab) {
                    ForEach(Tab.allCases) { t in
                        Text(t.label).tag(t)
                    }
                }
                .pickerStyle(.segmented)
                .frame(width: 220)
            }

            switch tab {
            case .apps:
                aliasesGrid(items: apps,
                            empty: "No app aliases yet. Tap Edit to add some.",
                            symbol: "app.fill",
                            tap: onAppTap)
            case .groups:
                aliasesGrid(items: groups,
                            empty: "No groups yet. Tap Edit to add some.",
                            symbol: "square.stack.3d.up.fill",
                            tap: onGroupTap)
            case .url:
                urlForm
            }

            HStack {
                Spacer()
                Button(editingAliases ? "Done" : "Edit aliases") {
                    editingAliases.toggle()
                }
                .font(.caption.weight(.medium))
                .foregroundStyle(Theme.textSecondary)
            }
            if editingAliases {
                aliasEditor
            }
        }
        .card()
    }

    @ViewBuilder
    private func aliasesGrid(items: [String], empty: String, symbol: String, tap: @escaping (String) -> Void) -> some View {
        if items.isEmpty {
            Text(empty)
                .font(.subheadline)
                .foregroundStyle(Theme.textMuted)
                .frame(maxWidth: .infinity, minHeight: 80)
        } else {
            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: 10),
                GridItem(.flexible(), spacing: 10),
                GridItem(.flexible(), spacing: 10),
            ], spacing: 10) {
                ForEach(items, id: \.self) { alias in
                    Button {
                        tap(alias)
                    } label: {
                        AliasTile(alias: alias, symbol: symbol)
                    }
                    .disabled(!pcOnline || pending != nil)
                    .opacity(!pcOnline || pending != nil ? 0.6 : 1)
                }
            }
        }
    }

    private var urlForm: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Open URL on PC").sectionTitleStyle()
            HStack {
                HStack(spacing: 8) {
                    Image(systemName: "globe").foregroundStyle(Theme.textSecondary)
                    TextField("https://youtube.com", text: $url)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                        .foregroundStyle(Theme.textPrimary)
                }
                .padding(.horizontal, 12).padding(.vertical, 10)
                .background(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(Theme.surfaceHover)
                )

                Button {
                    let normalized = normalize(url)
                    if !normalized.isEmpty { onURLSubmit(normalized); url = "" }
                } label: {
                    Image(systemName: "paperplane.fill")
                        .foregroundStyle(Theme.accent)
                        .padding(.horizontal, 12).padding(.vertical, 10)
                        .background(
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .fill(Theme.accentSoft)
                        )
                }
                .disabled(!pcOnline || url.isEmpty)
                .opacity(!pcOnline || url.isEmpty ? 0.5 : 1)
            }
            Text("Subject to your url_policy on the PC.")
                .font(.caption2)
                .foregroundStyle(Theme.textMuted)
        }
    }

    private var aliasEditor: some View {
        VStack(alignment: .leading, spacing: 10) {
            VStack(alignment: .leading, spacing: 4) {
                Text("App aliases").sectionTitleStyle()
                TextField("comma,separated,aliases", text: $appsCSV)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .padding(.horizontal, 12).padding(.vertical, 10)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(Theme.surfaceHover)
                    )
                    .foregroundStyle(Theme.textPrimary)
            }
            VStack(alignment: .leading, spacing: 4) {
                Text("Group aliases").sectionTitleStyle()
                TextField("comma,separated,aliases", text: $groupsCSV)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .padding(.horizontal, 12).padding(.vertical, 10)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(Theme.surfaceHover)
                    )
                    .foregroundStyle(Theme.textPrimary)
            }
            Text("These are display hints only. The PC's whitelist.yaml decides what's actually allowed.")
                .font(.caption2)
                .foregroundStyle(Theme.textMuted)
        }
    }

    private func normalize(_ raw: String) -> String {
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty { return "" }
        if trimmed.lowercased().hasPrefix("http://") || trimmed.lowercased().hasPrefix("https://") {
            return trimmed
        }
        return "https://" + trimmed
    }
}

private struct AliasTile: View {
    let alias: String
    let symbol: String

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            ZStack {
                RoundedRectangle(cornerRadius: 9, style: .continuous)
                    .fill(Theme.accentSoft)
                    .frame(width: 28, height: 28)
                Image(systemName: symbol)
                    .font(.footnote)
                    .foregroundStyle(Theme.accent)
            }
            Text(alias)
                .font(.subheadline.weight(.medium))
                .foregroundStyle(Theme.textPrimary)
                .lineLimit(1)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .frame(height: 78)
        .background(
            RoundedRectangle(cornerRadius: Theme.tileCorner, style: .continuous)
                .fill(Theme.surfaceHover.opacity(0.7))
        )
    }
}

import Foundation
import SwiftUI

/// Persisted credentials and the API client.
@MainActor
final class SessionStore: ObservableObject {
    @AppStorage("axon.baseUrl") var baseUrl: String = ""
    @AppStorage("axon.token")   var token: String   = ""
    @Published var isAuthenticated: Bool = false

    init() {
        self.isAuthenticated = !baseUrl.isEmpty && !token.isEmpty
    }

    func signIn(baseUrl: String, token: String) {
        self.baseUrl = baseUrl.trimmingCharacters(in: .whitespacesAndNewlines)
            .replacingOccurrences(of: "/+$", with: "", options: .regularExpression)
        self.token = token.trimmingCharacters(in: .whitespacesAndNewlines)
        isAuthenticated = !self.baseUrl.isEmpty && !self.token.isEmpty
    }

    func signOut() {
        baseUrl = ""
        token = ""
        isAuthenticated = false
    }

    var client: RelayClient { RelayClient(baseUrl: baseUrl, token: token) }
}

enum RelayError: Error, LocalizedError {
    case invalidURL
    case unauthorized
    case http(Int, String)
    case decoding(String)
    case network(String)

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Relay URL is invalid."
        case .unauthorized: return "The relay rejected the bearer token."
        case .http(let code, let body): return "HTTP \(code): \(body)"
        case .decoding(let m): return "Decoding error: \(m)"
        case .network(let m): return "Network error: \(m)"
        }
    }
}

struct RelayClient {
    let baseUrl: String
    let token: String

    private static let session: URLSession = {
        let cfg = URLSessionConfiguration.default
        cfg.timeoutIntervalForRequest = 12
        cfg.timeoutIntervalForResource = 20
        cfg.waitsForConnectivity = false
        return URLSession(configuration: cfg)
    }()

    private func makeRequest(_ path: String, method: String = "GET", body: Data? = nil) throws -> URLRequest {
        guard var comps = URLComponents(string: baseUrl) else { throw RelayError.invalidURL }
        comps.path = (comps.path.isEmpty ? "" : comps.path) + path
        guard let url = comps.url else { throw RelayError.invalidURL }
        var r = URLRequest(url: url)
        r.httpMethod = method
        r.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        if body != nil {
            r.setValue("application/json", forHTTPHeaderField: "Content-Type")
            r.httpBody = body
        }
        return r
    }

    func probe() async throws -> Bool {
        let req = try makeRequest("/healthz")
        let (data, resp) = try await Self.session.data(for: req)
        guard let http = resp as? HTTPURLResponse else { return false }
        if http.statusCode == 200, String(data: data, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) == "ok" {
            return true
        }
        return false
    }

    func status() async throws -> RelayStatus {
        let req = try makeRequest("/v1/status")
        let (data, resp) = try await Self.session.data(for: req)
        try validate(resp, data)
        do {
            return try JSONDecoder().decode(RelayStatus.self, from: data)
        } catch {
            throw RelayError.decoding(String(describing: error))
        }
    }

    func audit(limit: Int = 50) async throws -> [AuditEvent] {
        let req = try makeRequest("/v1/audit?limit=\(limit)")
        let (data, resp) = try await Self.session.data(for: req)
        try validate(resp, data)
        struct Wrap: Decodable { let events: [AuditEvent]; let limit: Int }
        do {
            return try JSONDecoder().decode(Wrap.self, from: data).events
        } catch {
            throw RelayError.decoding(String(describing: error))
        }
    }

    func send(_ name: CommandName, args: [String: Any] = [:]) async throws -> CommandResponse {
        let payload = CommandPayload.make(name, args: args)
        let body = try JSONEncoder().encode(payload)
        let req = try makeRequest("/v1/cmd", method: "POST", body: body)
        let (data, resp) = try await Self.session.data(for: req)
        guard let http = resp as? HTTPURLResponse else {
            throw RelayError.network("no response")
        }
        if http.statusCode == 401 { throw RelayError.unauthorized }
        // The relay returns structured JSON for 2xx, 4xx, 5xx alike (within reason).
        do {
            return try JSONDecoder().decode(CommandResponse.self, from: data)
        } catch {
            let body = String(data: data, encoding: .utf8) ?? ""
            throw RelayError.http(http.statusCode, body)
        }
    }

    private func validate(_ resp: URLResponse, _ data: Data) throws {
        guard let http = resp as? HTTPURLResponse else {
            throw RelayError.network("no response")
        }
        if http.statusCode == 401 { throw RelayError.unauthorized }
        if !(200..<300).contains(http.statusCode) {
            throw RelayError.http(http.statusCode, String(data: data, encoding: .utf8) ?? "")
        }
    }
}

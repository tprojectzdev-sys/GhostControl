import Foundation

/// Wire-format models. Mirrored 1:1 with relay/schemas.py and the web client.
enum CommandName: String, Codable, CaseIterable, Identifiable {
    case powerShutdown = "power.shutdown"
    case powerRestart  = "power.restart"
    case powerSleep    = "power.sleep"
    case powerLock     = "power.lock"
    case powerWake     = "power.wake"
    case appOpen       = "app.open"
    case urlOpen       = "url.open"
    case groupRun      = "group.run"
    case statusGet     = "status.get"

    var id: String { rawValue }

    var isDestructive: Bool {
        self == .powerShutdown || self == .powerRestart
    }
    var requiresBridge: Bool { self == .powerWake }
    var requiresPC: Bool {
        switch self {
        case .powerShutdown, .powerRestart, .powerSleep, .powerLock,
             .appOpen, .urlOpen, .groupRun, .statusGet:
            return true
        case .powerWake:
            return false
        }
    }
}

struct CommandPayload: Codable {
    var id: String
    var ts: Int
    var cmd: String
    var args: [String: AnyCodable]

    static func make(_ name: CommandName, args: [String: Any] = [:]) -> CommandPayload {
        CommandPayload(
            id: UUID().uuidString,
            ts: Int(Date().timeIntervalSince1970),
            cmd: name.rawValue,
            args: args.mapValues(AnyCodable.init)
        )
    }
}

struct CommandResponse: Codable {
    var status: String
    var id: String?
    var code: String?
    var message: String?
    var data: [String: AnyCodable]?
    var latency_ms: Int?
    var retry_after_seconds: Double?
    var role: String?
}

struct AgentStatus: Codable {
    var agent_id: String
    var role: String
    var connected_at: Int
    var last_seen: Int
    var uptime_seconds: Int
    var status: AgentStatusInner
}

struct AgentStatusInner: Codable {
    var online: Bool?
    var uptime_seconds: Int?
    var cpu_pct: Double?
    var ram_pct: Double?
    var idle_seconds: Int?
    var foreground_app: String?
    var os: String?
    var hostname: String?
}

struct RelayStatus: Codable {
    var pc: AgentStatus?
    var bridge: AgentStatus?
    var now: Int
}

struct AuditEvent: Codable, Identifiable {
    var ts_ms: Int
    var kind: String
    var id: String?
    var cmd: String?
    var args: [String: AnyCodable]?
    var route_to: String?
    var outcome: String?
    var ack_code: String?
    var ack_message: String?
    var src_ip: String?
    var role: String?
    var agent_id: String?
    var os: String?
    var hostname: String?

    // Identifiable shim — the relay does NOT guarantee `id` is unique across
    // event kinds (agent_connect events have no id), so we synthesize one.
    private enum CodingKeys: String, CodingKey {
        case ts_ms, kind, id, cmd, args, route_to, outcome,
             ack_code, ack_message, src_ip, role, agent_id, os, hostname
    }

    var stableID: String { "\(ts_ms)-\(kind)-\(id ?? agent_id ?? "")" }
}

// MARK: - AnyCodable
// Tiny helper so [String: Any] survives JSON round-trips without us
// importing a third-party package. Supports the JSON value types only.

struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) { self.value = value }

    init(from decoder: Decoder) throws {
        let c = try decoder.singleValueContainer()
        if c.decodeNil() { value = NSNull() }
        else if let b = try? c.decode(Bool.self) { value = b }
        else if let i = try? c.decode(Int.self) { value = i }
        else if let d = try? c.decode(Double.self) { value = d }
        else if let s = try? c.decode(String.self) { value = s }
        else if let arr = try? c.decode([AnyCodable].self) { value = arr.map { $0.value } }
        else if let obj = try? c.decode([String: AnyCodable].self) {
            value = obj.mapValues { $0.value }
        } else {
            throw DecodingError.dataCorruptedError(in: c, debugDescription: "Unsupported value")
        }
    }

    func encode(to encoder: Encoder) throws {
        var c = encoder.singleValueContainer()
        switch value {
        case is NSNull: try c.encodeNil()
        case let b as Bool: try c.encode(b)
        case let i as Int: try c.encode(i)
        case let d as Double: try c.encode(d)
        case let s as String: try c.encode(s)
        case let arr as [Any]: try c.encode(arr.map(AnyCodable.init))
        case let obj as [String: Any]: try c.encode(obj.mapValues(AnyCodable.init))
        default:
            throw EncodingError.invalidValue(value, .init(codingPath: c.codingPath, debugDescription: "Unsupported"))
        }
    }
}

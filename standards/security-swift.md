# Security — Swift / iOS

Follows general principles in [security.md](security.md) and [OWASP MASVS v2](https://mas.owasp.org/MASVS/).

## OWASP MASVS Overview

The Mobile Application Security Verification Standard defines three levels:
- **L1 (Standard)** — All apps: basic storage, network, auth, code quality
- **L2 (Defense-in-Depth)** — Sensitive-data apps: adds anti-tampering, advanced crypto, root detection
- **R (Resilience)** — High-value targets: adds obfuscation, anti-debugging, integrity verification

## Secure Data Storage

### Keychain

Store all sensitive credentials (tokens, passwords, keys) in the iOS Keychain:

```swift
import Security

func storeCredential(key: String, data: Data) throws {
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrAccount as String: key,
        kSecValueData as String: data,
        kSecAttrAccessible as String: kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly,
    ]

    let status = SecItemAdd(query as CFDictionary, nil)
    guard status == errSecSuccess else {
        throw KeychainError.unableToStore(status)
    }
}
```

**Rules:**
- Use `kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly` for most sensitive data
- Never store secrets in `UserDefaults`, `.plist` files, or hardcoded strings
- Exclude sensitive data from backups: `isExcludedFromBackup = true`
- CoreData does not encrypt by default — add encryption at the application layer if storing sensitive data

### File Protection

```swift
try data.write(to: url, options: .completeFileProtection)
```

Use `FileProtectionType.complete` for encrypted file storage — files are inaccessible when the device is locked.

## Cryptography

### Use Apple CryptoKit

```swift
import CryptoKit

// Symmetric encryption
let key = SymmetricKey(size: .bits256)
let sealedBox = try AES.GCM.seal(plaintext, using: key)
let decrypted = try AES.GCM.open(sealedBox, using: key)

// Hashing
let digest = SHA256.hash(data: data)

// HMAC
let authCode = HMAC<SHA256>.authenticationCode(for: data, using: key)
```

**Rules:**
- Never roll your own crypto — use CryptoKit exclusively
- Minimum key lengths: RSA 2048-bit, AES 128-bit (prefer 256-bit)
- Never hardcode encryption keys or IVs in source code
- Use `SecRandomCopyBytes` or CryptoKit for cryptographically secure random numbers

### Secure Data Wiping

```swift
// String cannot be reliably zeroed — use [UInt8] or Data for sensitive values
var sensitiveBytes = [UInt8](repeating: 0, count: 32)
defer {
    sensitiveBytes.withUnsafeMutableBufferPointer { buffer in
        memset_s(buffer.baseAddress, buffer.count, 0, buffer.count)
    }
}
```

`String` is copy-on-write and cannot be securely wiped from memory. Use `[UInt8]` or `Data` for sensitive values, and zero them when done.

## Network Security

### App Transport Security (ATS)

- **Never** add blanket `NSAllowsArbitraryLoads` exceptions in `Info.plist`
- If an exception is needed, scope it to a specific domain with justification
- All API communication must use HTTPS exclusively

### Certificate Pinning

```swift
// Implement via URLSessionDelegate for high-security endpoints
func urlSession(
    _ session: URLSession,
    didReceive challenge: URLAuthenticationChallenge,
    completionHandler: @escaping (URLSession.AuthChallengeDisposition, URLCredential?) -> Void
) {
    guard let serverTrust = challenge.protectionSpace.serverTrust,
          let certificate = SecTrustGetCertificateAtIndex(serverTrust, 0) else {
        completionHandler(.cancelAuthenticationChallenge, nil)
        return
    }

    let serverCertData = SecCertificateCopyData(certificate) as Data
    let pinnedCertData = loadPinnedCertificate()

    if serverCertData == pinnedCertData {
        completionHandler(.useCredential, URLCredential(trust: serverTrust))
    } else {
        completionHandler(.cancelAuthenticationChallenge, nil)
    }
}
```

**Rules:**
- Use `URLSession` or `Network.framework` for all network calls
- Never disable TLS validation, even in debug builds
- Validate all TLS certificates

## Authentication

### Biometric Authentication

```swift
import LocalAuthentication

func authenticateWithBiometrics() async throws -> Bool {
    let context = LAContext()
    var error: NSError?

    guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
        throw AuthError.biometricsUnavailable
    }

    return try await context.evaluatePolicy(
        .deviceOwnerAuthenticationWithBiometrics,
        localizedReason: "Authenticate to access your account"
    )
}
```

**Rules:**
- Integrate biometric auth with Keychain-backed keys for strongest security
- Use short-lived access tokens with refresh token rotation
- Never store plain-text passwords anywhere on device
- All authentication must be validated server-side — never trust client-only checks

## Platform Security

### URL Scheme and Universal Link Validation

```swift
func application(
    _ app: UIApplication,
    open url: URL,
    options: [UIApplication.OpenURLOptionsKey: Any] = [:]
) -> Bool {
    guard let components = URLComponents(url: url, resolvingAgainstBaseURL: true),
          components.scheme == "myapp",
          allowedHosts.contains(components.host ?? "") else {
        return false
    }
    return handleDeepLink(components)
}
```

Validate all URL schemes and Universal Links before processing.

### WebView Security

- Use `WKWebView` — never `UIWebView`
- Disable JavaScript if not needed
- Never use `@objc` exposed methods without proper validation

### Permissions

- Request only necessary permissions
- Provide clear purpose strings in `NSCameraUsageDescription`, `NSLocationWhenInUseUsageDescription`, etc.
- Disable pasteboard sharing for sensitive text fields

## Concurrency Safety

### Actor Isolation

```swift
// Use @MainActor for all UI-bound types
@MainActor
class ProfileViewModel: ObservableObject {
    @Published var user: User?

    func loadUser() async {
        user = try? await userService.fetchCurrentUser()
    }
}

// Use custom actors for shared mutable state
actor TokenStore {
    private var token: String?

    func setToken(_ newToken: String) {
        token = newToken
    }

    func getToken() -> String? {
        token
    }
}
```

**Rules:**
- Use `Sendable` and actor isolation to prevent data races (Swift 6 strict concurrency)
- Prefer `struct` over `class` for data models — value semantics prevent shared mutable state
- Use `#if DEBUG` / `#if targetEnvironment(simulator)` to gate debug-only code paths

## Code Quality

### Compiler Flags

- Enable all compiler security flags: `-fstack-protector-all`, PIE, ARC
- Set minimum deployment target to a currently supported iOS version
- Compile with zero warnings

### Input Validation

- Validate and sanitize all untrusted inputs: deep links, clipboard, IPC
- Use `@frozen` for public enums in library code to prevent injection

### Logging

- Disable verbose/debug logging in production builds
- Never log sensitive data (tokens, passwords, PII)

```swift
#if DEBUG
func debugLog(_ message: String) {
    print("[DEBUG] \(message)")
}
#else
func debugLog(_ message: String) { }
#endif
```

## Dependency Security

- Audit third-party dependencies for known vulnerabilities regularly
- Pin dependency versions in `Package.swift` or `Podfile.lock`
- Review new dependencies before adding — check maintenance status, license, and security history

## Security Checklist — iOS

- [ ] Sensitive data stored in Keychain, not UserDefaults
- [ ] File protection enabled for sensitive files
- [ ] ATS enforced — no blanket exceptions
- [ ] Certificate pinning on high-security endpoints
- [ ] Biometric auth integrated with Keychain
- [ ] CryptoKit used for all cryptographic operations
- [ ] No hardcoded secrets in source code
- [ ] Debug logging stripped from production
- [ ] URL schemes and deep links validated
- [ ] Permissions minimized with clear purpose strings
- [ ] Dependencies audited and pinned
- [ ] Strict concurrency (`Sendable`, actors) for data race prevention

## References

- [OWASP MASVS v2](https://mas.owasp.org/MASVS/)
- [OWASP MASTG (iOS)](https://mas.owasp.org/MASTG/)
- [Apple Security Documentation](https://developer.apple.com/documentation/security)
- [Apple CryptoKit](https://developer.apple.com/documentation/cryptokit)
- [Apple LocalAuthentication](https://developer.apple.com/documentation/localauthentication)

# Security — Swift / iOS

Follows [security.md](../security.md) and [OWASP MASVS v2](https://mas.owasp.org/MASVS/).

## Keychain

Store all sensitive credentials in the iOS Keychain:

```swift
func storeCredential(key: String, data: Data) throws {
    let query: [String: Any] = [
        kSecClass as String: kSecClassGenericPassword,
        kSecAttrAccount as String: key,
        kSecValueData as String: data,
        kSecAttrAccessible as String: kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly,
    ]
    let status = SecItemAdd(query as CFDictionary, nil)
    guard status == errSecSuccess else { throw KeychainError.unableToStore(status) }
}
```

- Use `kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly` for most sensitive data
- Never store secrets in UserDefaults, .plist, or hardcoded strings
- CoreData does not encrypt by default — add application-layer encryption for sensitive data

## Cryptography (CryptoKit)

```swift
import CryptoKit

let key = SymmetricKey(size: .bits256)
let sealedBox = try AES.GCM.seal(plaintext, using: key)
let decrypted = try AES.GCM.open(sealedBox, using: key)
```

- Never roll your own crypto; never hardcode keys/IVs
- Minimum: RSA 2048-bit, AES 128-bit (prefer 256-bit)
- String cannot be reliably zeroed — use `[UInt8]` or `Data` for sensitive values

## Network Security

- **Never** add blanket `NSAllowsArbitraryLoads`; scope exceptions to specific domains
- Certificate pinning via `URLSessionDelegate` for high-security endpoints
- Never disable TLS validation, even in debug builds

## Biometric Authentication

```swift
import LocalAuthentication

func authenticateWithBiometrics() async throws -> Bool {
    let context = LAContext()
    return try await context.evaluatePolicy(
        .deviceOwnerAuthenticationWithBiometrics,
        localizedReason: "Authenticate to access your account"
    )
}
```

- Integrate with Keychain-backed keys; short-lived tokens with refresh rotation
- All authentication validated server-side

## Concurrency Safety

- `@MainActor` for UI-bound types; custom `actor` for shared mutable state
- `Sendable` and actor isolation for data race prevention (Swift 6)
- Prefer `struct` over `class` for data models
- `#if DEBUG` / `#if targetEnvironment(simulator)` for debug-only paths

## Platform Rules

- WebView: use `WKWebView` only; disable JavaScript unless needed
- Permissions: request only necessary ones; clear purpose strings
- Compiler: enable all security flags; minimum supported iOS version; zero warnings
- Logging: disable verbose/debug in production; never log sensitive data

## Security Checklist — iOS

- [ ] Sensitive data in Keychain, not UserDefaults
- [ ] File protection enabled for sensitive files
- [ ] ATS enforced — no blanket exceptions
- [ ] Certificate pinning on high-security endpoints
- [ ] Biometric auth integrated with Keychain
- [ ] CryptoKit for all cryptographic operations
- [ ] No hardcoded secrets in source code
- [ ] Debug logging stripped from production
- [ ] URL schemes and deep links validated
- [ ] Permissions minimized with clear purpose strings
- [ ] Dependencies audited and pinned
- [ ] Strict concurrency (Sendable, actors) for data race prevention

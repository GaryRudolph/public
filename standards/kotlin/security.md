# Security — Kotlin / Android

Follows general principles in [security.md](../security.md) and [OWASP MASVS v2](https://mas.owasp.org/MASVS/).

## OWASP MASVS Overview

The Mobile Application Security Verification Standard defines three levels:
- **L1 (Standard)** — All apps: basic storage, network, auth, code quality
- **L2 (Defense-in-Depth)** — Sensitive-data apps: adds anti-tampering, advanced crypto, root detection
- **R (Resilience)** — High-value targets: adds obfuscation, anti-debugging, integrity verification

## Secure Data Storage

### EncryptedSharedPreferences

Store sensitive key-value data (tokens, credentials) using Jetpack Security:

```kotlin
import androidx.security.crypto.EncryptedSharedPreferences
import androidx.security.crypto.MasterKey

val masterKey = MasterKey.Builder(context)
    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
    .build()

val prefs = EncryptedSharedPreferences.create(
    context,
    "secure_prefs",
    masterKey,
    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
)

// Use like normal SharedPreferences
prefs.edit().putString("auth_token", token).apply()
```

### Android Keystore

Use the hardware-backed Keystore for cryptographic key storage — keys never leave the secure hardware:

```kotlin
import java.security.KeyStore
import javax.crypto.KeyGenerator
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties

fun generateKey(alias: String) {
    val keyGenerator = KeyGenerator.getInstance(
        KeyProperties.KEY_ALGORITHM_AES,
        "AndroidKeyStore",
    )
    keyGenerator.init(
        KeyGenParameterSpec.Builder(
            alias,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT,
        )
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setUserAuthenticationRequired(true)
            .build()
    )
    keyGenerator.generateKey()
}
```

### EncryptedFile

```kotlin
import androidx.security.crypto.EncryptedFile

val encryptedFile = EncryptedFile.Builder(
    context,
    file,
    masterKey,
    EncryptedFile.FileEncryptionScheme.AES256_GCM_HKDF_4KB,
).build()

encryptedFile.openFileOutput().use { output ->
    output.write(sensitiveData)
}
```

### Storage Rules

- **Never** store secrets (API keys, tokens) in `BuildConfig`, `strings.xml`, or source code
- Use `DataStore` (Proto) over `SharedPreferences` for non-sensitive structured data — coroutine-safe, type-safe
- Exclude sensitive data from backups: `android:allowBackup="false"` or exclude specific files in backup rules

## Network Security

### Network Security Configuration

Enforce TLS for all communication:

```xml
<!-- res/xml/network_security_config.xml -->
<network-security-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
</network-security-config>
```

Reference in `AndroidManifest.xml`:

```xml
<application
    android:networkSecurityConfig="@xml/network_security_config"
    ... >
```

### Certificate Pinning

```xml
<!-- In network_security_config.xml -->
<domain-config>
    <domain includeSubdomains="true">api.example.com</domain>
    <pin-set expiration="2026-01-01">
        <pin digest="SHA-256">base64EncodedPin1=</pin>
        <pin digest="SHA-256">base64EncodedPin2=</pin>
    </pin-set>
</domain-config>
```

Programmatic alternative with OkHttp:

```kotlin
val client = OkHttpClient.Builder()
    .certificatePinner(
        CertificatePinner.Builder()
            .add("api.example.com", "sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")
            .build()
    )
    .build()
```

## Authentication

### Biometric Authentication

```kotlin
import androidx.biometric.BiometricPrompt

val promptInfo = BiometricPrompt.PromptInfo.Builder()
    .setTitle("Authenticate")
    .setSubtitle("Verify your identity")
    .setNegativeButtonText("Cancel")
    .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
    .build()

val biometricPrompt = BiometricPrompt(
    activity,
    executor,
    object : BiometricPrompt.AuthenticationCallback() {
        override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
            val cryptoObject = result.cryptoObject
            // Use Keystore-bound key from cryptoObject
        }

        override fun onAuthenticationError(errorCode: Int, errString: CharSequence) {
            handleAuthError(errorCode, errString)
        }
    },
)

biometricPrompt.authenticate(promptInfo, cryptoObject)
```

**Rules:**
- Back biometric authentication with Keystore-bound keys
- Use `OAuth 2.0` / `OIDC` with PKCE for authentication flows
- Never trust client-side-only validation — always validate server-side

## Platform Security

### ProGuard / R8

Enable in release builds:

```kotlin
// build.gradle.kts
android {
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro",
            )
        }
    }
}
```

ProGuard rules:

```
# Strip debug logging
-assumenosideeffects class android.util.Log {
    public static int d(...);
    public static int v(...);
}
```

**Rules:**
- Use `-keep` rules judiciously — over-keeping defeats obfuscation
- Test proguarded builds thoroughly; use `-printusage` to audit removed code
- Beware of Kotlin string interpolation leaving `StringBuilder` artifacts — use a custom logger wrapper that R8 can fully strip

### Play Integrity API

Use Play Integrity API (replacement for deprecated SafetyNet) to verify device and app integrity.

### Screen Security

```kotlin
// Prevent screenshots of sensitive screens
window.setFlags(
    WindowManager.LayoutParams.FLAG_SECURE,
    WindowManager.LayoutParams.FLAG_SECURE,
)
```

### WebView Security

```kotlin
webView.settings.apply {
    javaScriptEnabled = false // Enable only when explicitly required
    allowFileAccess = false
    allowContentAccess = false
}
// Use @JavascriptInterface sparingly and validate all inputs
```

### Permissions

- Apply **least privilege** — request only necessary permissions
- Justify each permission in the privacy manifest
- Request permissions at the time of use, not at app launch

## Input Validation

- Validate all input — server-side and client-side
- Never trust client-side-only validation
- Handle errors without exposing stack traces or internal details to users

## Logging

- Strip `android.util.Log` calls from release builds via ProGuard/R8
- Never log sensitive data (tokens, passwords, PII)
- Use a custom logger wrapper to control log levels by build type

## Dependency Security

- Pin dependency versions in `build.gradle.kts`
- Use Gradle dependency verification (`gradle/verification-metadata.xml`)
- Audit dependencies for known vulnerabilities regularly
- Review new dependencies before adding — check maintenance status, license, and security history

## Security Checklist — Android

- [ ] Sensitive data stored in EncryptedSharedPreferences or Android Keystore
- [ ] Encrypted files via EncryptedFile for sensitive documents
- [ ] `cleartextTrafficPermitted="false"` in network security config
- [ ] Certificate pinning on high-security endpoints
- [ ] Biometric auth backed by Keystore-bound keys
- [ ] R8/ProGuard enabled with log stripping in release
- [ ] No hardcoded secrets in source code, BuildConfig, or resources
- [ ] `FLAG_SECURE` on sensitive screens
- [ ] WebView JavaScript disabled unless explicitly required
- [ ] `allowBackup="false"` or backup rules excluding sensitive data
- [ ] Play Integrity API integrated
- [ ] Permissions minimized and justified
- [ ] Dependencies pinned and audited

## References

- [OWASP MASVS v2](https://mas.owasp.org/MASVS/)
- [OWASP MASTG (Android)](https://mas.owasp.org/MASTG/)
- [Android Security Best Practices](https://developer.android.com/topic/security/best-practices)
- [Jetpack Security](https://developer.android.com/topic/security/data)
- [Network Security Configuration](https://developer.android.com/privacy-and-security/security-config)
- [BiometricPrompt](https://developer.android.com/reference/androidx/biometric/BiometricPrompt)

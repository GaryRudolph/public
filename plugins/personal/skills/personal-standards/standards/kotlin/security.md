# Security — Kotlin / Android

Follows [security.md](../security.md) and [OWASP MASVS v2](https://mas.owasp.org/MASVS/).

## EncryptedSharedPreferences

```kotlin
val masterKey = MasterKey.Builder(context)
    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
    .build()

val prefs = EncryptedSharedPreferences.create(
    context, "secure_prefs", masterKey,
    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM,
)
prefs.edit().putString("auth_token", token).apply()
```

## Android Keystore

Hardware-backed key storage — keys never leave secure hardware:

```kotlin
fun generateKey(alias: String) {
    val keyGenerator = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
    keyGenerator.init(
        KeyGenParameterSpec.Builder(alias,
            KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
            .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
            .setUserAuthenticationRequired(true)
            .build()
    )
    keyGenerator.generateKey()
}
```

## Storage Rules

- **Never** store secrets in `BuildConfig`, `strings.xml`, or source code
- Use `DataStore` (Proto) over `SharedPreferences` for non-sensitive structured data
- Exclude sensitive data from backups: `android:allowBackup="false"`

## Network Security

Enforce TLS:

```xml
<network-security-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors><certificates src="system" /></trust-anchors>
    </base-config>
</network-security-config>
```

Certificate pinning via network config or OkHttp `CertificatePinner`.

## Biometric Authentication

```kotlin
val promptInfo = BiometricPrompt.PromptInfo.Builder()
    .setTitle("Authenticate")
    .setNegativeButtonText("Cancel")
    .setAllowedAuthenticators(BiometricManager.Authenticators.BIOMETRIC_STRONG)
    .build()
```

Back biometric auth with Keystore-bound keys. All auth validated server-side.

## ProGuard / R8

```kotlin
android {
    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
        }
    }
}
```

Strip debug logging in release:
```
-assumenosideeffects class android.util.Log {
    public static int d(...);
    public static int v(...);
}
```

## Platform Rules

- **Play Integrity API** for device/app integrity verification
- **`FLAG_SECURE`** on sensitive screens to prevent screenshots
- WebView: `javaScriptEnabled = false` unless explicitly required
- Permissions: least privilege, justify each, request at time of use
- Logging: strip in release builds, never log sensitive data

## Security Checklist — Android

- [ ] Sensitive data in EncryptedSharedPreferences or Keystore
- [ ] `cleartextTrafficPermitted="false"` in network config
- [ ] Certificate pinning on high-security endpoints
- [ ] Biometric auth backed by Keystore-bound keys
- [ ] R8/ProGuard enabled with log stripping in release
- [ ] No hardcoded secrets in source, BuildConfig, or resources
- [ ] `FLAG_SECURE` on sensitive screens
- [ ] WebView JavaScript disabled unless required
- [ ] `allowBackup="false"` or backup rules excluding sensitive data
- [ ] Play Integrity API integrated
- [ ] Permissions minimized and justified
- [ ] Dependencies pinned and audited

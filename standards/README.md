# Coding Standards

This directory contains coding standards for consistent, maintainable, quality code. They also serve as context for AI coding agents.

## Core Standards

- **[Code Style](code-style.md)** — Naming conventions, formatting, imports, anti-patterns
- **[Architecture](architecture.md)** — Layering, DI, API design, error handling
- **[Platform Parity](platform-parity.md)** — Cross-platform Swift/Kotlin naming and layer conventions
- **[Testing](testing.md)** — Coverage targets, test structure, mocking rules
- **[Documentation](documentation.md)** — What to document, ADR format, TODO conventions
- **[Git Workflow](git.md)** — Branching, versioning, commit format, PR workflow
- **[Security](security.md)** — Auth, encryption, input validation, checklists

## Language-Specific Standards

### Python
- **[Code Style](python/code-style.md)** — PEP 8, Ruff/Black, type annotations, mypy
- **[Architecture](python/architecture.md)** — Patterns, DI, error catalog
- **[Testing](python/testing.md)** — pytest, Hypothesis, coverage, moto/AWS
- **[Documentation](python/documentation.md)** — Google-style docstrings, Sphinx
- **[Security](python/security.md)** — bcrypt, JWT, Flask security, Pydantic, Bandit

### Swift
- **[Code Style](swift/code-style.md)** — Apple API Guidelines, SwiftLint, access control
- **[Architecture](swift/architecture.md)** — Manager pattern, MVVM, Router, ManagerFactory
- **[Testing](swift/testing.md)** — Swift Testing, XCTest, snapshot testing
- **[Documentation](swift/documentation.md)** — `///` doc comments, DocC
- **[Security](swift/security.md)** — Keychain, ATS, CryptoKit, OWASP MASVS

### Kotlin
- **[Code Style](kotlin/code-style.md)** — JetBrains conventions, detekt/ktlint
- **[Architecture](kotlin/architecture.md)** — MVI, Compose state, coroutines
- **[Testing](kotlin/testing.md)** — JUnit 5, MockK, Turbine, Compose UI
- **[Documentation](kotlin/documentation.md)** — KDoc, Dokka
- **[Security](kotlin/security.md)** — EncryptedSharedPreferences, Keystore, ProGuard/R8

## Principles

- **Simplicity** — prefer simple solutions over complex ones
- **Consistency** — follow established patterns
- **Readability** — code is read more than written
- **Maintainability** — think about future developers
- **Security** — build security in from the start

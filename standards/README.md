# Coding Standards

This directory contains comprehensive coding standards for the project. These standards ensure consistency, maintainability, and quality across the codebase.

## Standards Documents

### Core Standards
- **[Code Style](code-style.md)** - Naming conventions, formatting principles, and code organization
- **[Architecture](architecture.md)** - Design patterns, module structure, cross-platform parity, and architectural decisions
- **[Testing](testing.md)** - Testing philosophy, coverage requirements, and cross-language patterns
- **[Documentation](documentation.md)** - Documentation requirements and formats

### Process Standards
- **[Git Workflow](git.md)** - Branching strategy, commit conventions, and PR process
- **[Security](security.md)** - Security principles, OWASP guidance, and cross-language patterns

### Language-Specific Standards

#### Python
- **[Code Style — Python](python/code-style.md)** - PEP 8, Ruff/Black config, type annotations, mypy
- **[Documentation — Python](python/documentation.md)** - Google-style docstrings, Sphinx
- **[Testing — Python](python/testing.md)** - pytest, Hypothesis, coverage, fixtures, moto/AWS, integration patterns
- **[Security — Python](python/security.md)** - bcrypt, JWT, Flask security, Pydantic, Bandit, cryptography

#### Swift
- **[Code Style — Swift](swift/code-style.md)** - Apple API Guidelines, SwiftLint, access control
- **[Documentation — Swift](swift/documentation.md)** - `///` doc comments, DocC catalogs
- **[Testing — Swift](swift/testing.md)** - Swift Testing, XCTest, snapshot testing, UI testing
- **[Security — Swift](swift/security.md)** - Keychain, ATS, CryptoKit, OWASP MASVS

#### Kotlin
- **[Code Style — Kotlin](kotlin/code-style.md)** - JetBrains conventions, detekt/ktlint, idioms
- **[Documentation — Kotlin](kotlin/documentation.md)** - KDoc, Dokka
- **[Testing — Kotlin](kotlin/testing.md)** - JUnit 5, MockK, Turbine, Compose UI testing
- **[Security — Kotlin](kotlin/security.md)** - EncryptedSharedPreferences, Android Keystore, OWASP MASVS

## Purpose

These standards serve as:
- **Reference for developers** - Clear guidelines for writing consistent code
- **AI agent instructions** - Context for code generation and modifications
- **Code review criteria** - Baseline expectations for code quality
- **Onboarding material** - Quick start for new team members

## How to Use

1. **Before starting work**: Review the relevant standard documents
2. **During development**: Reference standards for specific questions
3. **During code review**: Use as criteria for feedback
4. **When updating**: Submit changes to standards as PRs with rationale

## Principles

All standards are guided by these core principles:
- **Simplicity** - Prefer simple solutions over complex ones
- **Consistency** - Follow established patterns
- **Readability** - Code is read more than written
- **Maintainability** - Think about future developers
- **Security** - Build security in from the start

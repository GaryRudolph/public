# Coding Standards

This directory contains comprehensive coding standards for the project. These standards ensure consistency, maintainability, and quality across the codebase.

## Standards Documents

### Core Standards
- **[Code Style](code-style.md)** - Formatting rules, naming conventions, and code organization
- **[Architecture](architecture.md)** - Design patterns, module structure, and architectural decisions
- **[Testing](testing.md)** - Test coverage requirements, testing patterns, and best practices
- **[Documentation](documentation.md)** - Documentation requirements and formats

### Process Standards
- **[Git Workflow](git.md)** - Branching strategy, commit conventions, and PR process
- **[Security](security.md)** - Security requirements and vulnerability prevention

### Language-Specific Standards

#### Python
- **[Code Style — Python](code-style-python.md)** - PEP 8, Ruff/Black config, type annotations, mypy
- **[Documentation — Python](documentation-python.md)** - Google-style docstrings, Sphinx
- **[Testing — Python](testing-python.md)** - pytest, Hypothesis, coverage config, fixtures

#### Swift
- **[Code Style — Swift](code-style-swift.md)** - Apple API Guidelines, SwiftLint, access control
- **[Documentation — Swift](documentation-swift.md)** - `///` doc comments, DocC catalogs
- **[Testing — Swift](testing-swift.md)** - Swift Testing, XCTest, snapshot testing, UI testing
- **[Security — Swift](security-swift.md)** - Keychain, ATS, CryptoKit, OWASP MASVS

#### Kotlin
- **[Code Style — Kotlin](code-style-kotlin.md)** - JetBrains conventions, detekt/ktlint, idioms
- **[Documentation — Kotlin](documentation-kotlin.md)** - KDoc, Dokka
- **[Testing — Kotlin](testing-kotlin.md)** - JUnit 5, MockK, Turbine, Compose UI testing
- **[Security — Kotlin](security-kotlin.md)** - EncryptedSharedPreferences, Android Keystore, OWASP MASVS

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

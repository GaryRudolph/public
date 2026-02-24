# AI Agent Instructions

This document provides guidelines for AI coding agents and how I would
like them to work together with me.

## Coding Standards

All code generation and modifications should follow the standards defined in
the `standards/` directory of this repository:

### Core Standards

- **Code Style** (`standards/code-style.md`) - Formatting, naming conventions, and code organization
- **Architecture** (`standards/architecture.md`) - Design patterns and architectural principles
- **Testing** (`standards/testing.md`) - Testing strategy and best practices
- **Documentation** (`standards/documentation.md`) - Code documentation requirements
- **Git Workflow** (`standards/git.md`) - Commit messages and branching strategy
- **Security** (`standards/security.md`) - Security best practices and requirements

### Language-Specific Standards

When working with a specific language, also follow the corresponding
language-specific standards:

- **Python**: `standards/python/` (code-style, testing, documentation, security)
- **Swift**: `standards/swift/` (code-style, testing, documentation, security)
- **Kotlin**: `standards/kotlin/` (code-style, testing, documentation, security)

## Quick Reference

Before generating or modifying code:
1. Review the relevant standards documents
2. Follow established patterns in the existing codebase
3. Ensure all new code includes appropriate tests
4. Add documentation for public APIs and complex logic
5. Follow the commit message format defined in git standards

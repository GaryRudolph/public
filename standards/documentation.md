# Documentation Standards

## What to Document

**Always**: public APIs, complex business logic, architecture decisions, setup/configuration, non-obvious behavior, workarounds

**Don't**: self-explanatory code, implementation details that may change, what the code does (code should be self-documenting)

## Code Comments

- Explain **why**, not what
- Document non-obvious algorithms, performance trade-offs, and workarounds

### TODO Format

- `TODO:` — work to be done
- `TODO(username):` — assigned to someone
- `TODO: [TICKET-123]` — linked to a ticket
- `FIXME:` — known bug or broken behavior
- `HACK:` — temporary workaround, explain why and when to remove
- `NOTE:` — important context for the reader

## Architecture Decision Records

```markdown
# ADR-001: Title

## Status
Accepted | Proposed | Deprecated

## Context
Why a decision was needed.

## Decision
What was decided.

## Consequences
### Positive
### Negative

## Alternatives Considered
```

## Changelog

Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format: `Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`

## Documentation Review Checklist

- [ ] Accurate and up-to-date with code?
- [ ] Examples working and tested?
- [ ] Clear and easy to understand?
- [ ] Links working?
- [ ] Formatting consistent?

Include documentation changes in code reviews. Update docs in the same PR as code changes.

## Language-Specific Guidelines

- **[Python](python/documentation.md)**
- **[Swift](swift/documentation.md)**
- **[Kotlin](kotlin/documentation.md)**

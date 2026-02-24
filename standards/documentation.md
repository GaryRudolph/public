# Documentation Standards

## Documentation Philosophy

- **Documentation is code** - Keep it in version control, review it, maintain it
- **Write for humans** - Clear, concise, and helpful
- **Update with code** - Documentation should change when code changes
- **DRY applies** - Don't repeat what the code already says clearly
- **Just enough** - Document what's necessary, not everything

## What to Document

### Always Document
- **Public APIs** - All public functions, classes, and modules
- **Complex business logic** - Non-obvious algorithms and decisions
- **Architecture decisions** - Why things are structured a certain way
- **Setup and configuration** - How to get started
- **Non-obvious behavior** - Surprising or unexpected functionality
- **Workarounds** - Temporary fixes and why they exist

### Don't Document
- **Self-explanatory code** - Good naming makes comments unnecessary
- **Implementation details** - Internal workings that may change
- **What the code does** - Code should be self-documenting
- **Outdated information** - Remove or update stale docs immediately

## Code Comments

### When to Comment
- Explain **why**, not what
- Document non-obvious algorithms, performance trade-offs, and workarounds
- Avoid restating what the code clearly expresses

### TODO Comments
Use a consistent format so they're easy to search:
- `TODO:` — work to be done
- `TODO(username):` — assigned to someone
- `TODO: [TICKET-123]` — linked to a ticket
- `FIXME:` — known bug or broken behavior
- `HACK:` — temporary workaround, explain why and when to remove
- `NOTE:` — important context for the reader

## README Files

### Project README Structure
```markdown
# Project Name

Brief description of what the project does.

## Features
## Installation
## Quick Start
## Configuration
## Usage
## API Documentation
## Development
## Contributing
## License
```

### Module README
For complex modules within a project, include:
- What the module does and why it exists
- Directory structure
- Usage example
- Key architectural decisions
- How to run module-specific tests

## API Documentation

### REST API Documentation
Document each endpoint with: parameters, response shape, error codes, and a curl example.

### GraphQL Documentation
Use schema descriptions on all types and fields.

## Architecture Decision Records (ADRs)

Document significant architectural decisions:

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

Follow [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format with sections:
`Added`, `Changed`, `Deprecated`, `Removed`, `Fixed`, `Security`

## Documentation Review

### Checklist
- [ ] Is the documentation accurate?
- [ ] Is it up-to-date with the code?
- [ ] Are examples working and tested?
- [ ] Is it clear and easy to understand?
- [ ] Are there typos or grammatical errors?
- [ ] Are links working?
- [ ] Is the formatting consistent?

### Review Process
- Include documentation changes in code reviews
- Test examples and code snippets
- Update documentation in the same PR as code changes
- Have someone unfamiliar with the code review docs

## Best Practices

- **Be concise** - One clear sentence beats three vague ones
- **Use examples** - Show don't tell
- **Keep it updated** - Remove docs for deleted code; mark deprecated features
- **Link to resources** - Reference RFCs, issue trackers, upstream bugs

## Accessibility

- Use descriptive link text
- Include alt text for images
- Use semantic HTML in markdown
- Ensure good contrast in code examples

## Language-Specific Guidelines

- **[Python](python/documentation.md)**
- **[Swift](swift/documentation.md)**
- **[Kotlin](kotlin/documentation.md)**

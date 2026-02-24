# Architecture Standards

## Core Principles

- **Solve the current problem** — don't build for hypothetical futures; only abstract when you have 3+ concrete examples
- **Prefer boring technology** — established patterns and libraries over novel approaches
- **Separation of concerns** — business logic separate from presentation; data access separate from business logic; configuration separate from code

## Layered Architecture

```
┌─────────────────────────────────────┐
│     Presentation Layer              │  UI, Controllers, APIs
├─────────────────────────────────────┤
│     Business Logic Layer            │  Services, Domain Logic
├─────────────────────────────────────┤
│     Data Access Layer               │  Repositories, DAOs
├─────────────────────────────────────┤
│     Infrastructure Layer            │  Database, External APIs
└─────────────────────────────────────┘
```

Each layer only depends on layers below it. Never skip layers.

## Dependency Management

### Constructor Injection + Factory Builder

All dependencies via constructor. A single factory builder (composition root) wires everything. Classes never create their own collaborators.

- Classes are **testable** — call the constructor with mocks, no framework needed
- The **factory is the only place** that knows about concrete types
- Swapping an implementation requires changing one line in the factory

### Dependency Direction

High-level modules depend on abstractions (interfaces/protocols), not concrete implementations.

## Error Handling Layers

1. **Service Layer** — throws domain-specific errors
2. **Controller Layer** — catches and transforms to HTTP responses (or UI dialogs)
3. **Global Handler** — catches unexpected errors, logs, returns safe responses

## API Design

- Use HTTP verbs correctly; plural nouns for resources (`/users`, not `/user`)
- Version in URL: `/api/v1/users`
- Consistent response format:

```json
{ "data": { }, "meta": { } }

{ "error": { "code": "VALIDATION_ERROR", "message": "...", "details": [] } }
```

## State Management

- Keep state as local as possible
- Immutable data by default
- Single source of truth
- Predictable state updates

## Language-Specific Guidelines

- **[Python](python/architecture.md)**
- **[Swift](swift/architecture.md)**
- **[Kotlin](kotlin/architecture.md)**

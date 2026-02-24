# Architecture Standards

## Core Principles

### SOLID Principles
- **Single Responsibility** - Each module/class has one reason to change
- **Open/Closed** - Open for extension, closed for modification
- **Liskov Substitution** - Subtypes must be substitutable for base types
- **Interface Segregation** - Many specific interfaces > one general interface
- **Dependency Inversion** - Depend on abstractions, not concretions

### Keep It Simple
- Solve the current problem, not future hypothetical problems
- Prefer boring technology and established patterns
- Only abstract when you have 3+ concrete examples
- Avoid premature optimization

### Separation of Concerns
- Business logic separate from presentation
- Data access separate from business logic
- Configuration separate from code

## Architectural Patterns

### Layered Architecture

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

**Rules:**
- Each layer only depends on layers below it
- Never skip layers (presentation → data access)
- Keep layers thin and focused

### Hexagonal Architecture (Ports & Adapters)

An alternative to strict layering. The core domain is framework-independent — you can swap frameworks or data stores without touching business logic.

- **Ports**: abstract interfaces defining what the domain needs
- **Adapters**: concrete implementations of ports (e.g., `PostgresUserRepository` implements `UserRepository`)
- **The Dependency Rule**: inner layers never import from outer layers

```
┌──────────────────────────────────────────────┐
│                  Adapters                     │
│  ┌────────────────────────────────────────┐  │
│  │          Application Services          │  │
│  │  ┌──────────────────────────────────┐  │  │
│  │  │        Domain (pure logic)       │  │  │
│  │  │     No framework imports here    │  │  │
│  │  └──────────────────────────────────┘  │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

## Dependency Management

### Constructor Injection + Factory Builder

Favor **constructor injection** for all dependencies. Each class declares what it needs in its constructor and never creates its own collaborators. A single **factory builder** (or composition root) is responsible for wiring everything together. This keeps classes testable in isolation — tests call the constructor directly with mocks — while production code uses the factory.

**Why this matters:**
- Classes are **testable** — call the constructor with mocks, no framework needed
- The **factory builder is the only place** that knows about concrete types
- Swapping an implementation (e.g., a mock payment service) requires changing one line in the factory, not touching business logic
- **Avoid** classes that create their own dependencies internally — this hides coupling and makes testing difficult

### Dependency Direction
- High-level modules should not depend on low-level modules
- Both should depend on abstractions (interfaces/protocols)

## Error Handling Architecture

### Error Handling Layers
1. **Service Layer** - Throws domain-specific errors
2. **Controller Layer** - Catches and transforms to HTTP responses (or UI error dialogs in mobile)
3. **Global Handler** - Catches unexpected errors, logs, returns safe responses

## Data Flow

### Request Flow
```
HTTP Request
    ↓
Controller (validate, parse)
    ↓
Service (business logic)
    ↓
Repository (data access)
    ↓
Database
```

### Response Flow
```
Database
    ↓
Repository (domain models)
    ↓
Service (business logic)
    ↓
Controller (DTOs/serialization)
    ↓
HTTP Response
```

## State Management

### Principles
- Keep state as local as possible
- Immutable data by default
- Single source of truth
- Predictable state updates

## API Design

### RESTful Principles
- Use HTTP verbs correctly (GET, POST, PUT, DELETE)
- Use plural nouns for resources (`/users`, not `/user`)
- Use path parameters for IDs (`/users/123`)
- Use query parameters for filtering (`/users?status=active`)

### Versioning
- Include version in URL: `/api/v1/users`
- Maintain backward compatibility within a version
- Document breaking changes

### Response Format
```json
// Success response
{
  "data": { },
  "meta": { }
}

// Error response
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Validation failed",
    "details": [
      { "field": "email", "message": "Invalid email format" }
    ]
  }
}
```

## Performance Considerations

### When to Optimize
1. Measure first - don't guess
2. Focus on algorithmic complexity
3. Optimize hot paths only
4. Don't sacrifice readability for minor gains

### Caching Strategy
- Cache at appropriate layers
- Use cache invalidation strategies
- Consider cache consistency requirements

### Database Access
- Use connection pooling
- Avoid N+1 queries
- Use indexes on frequently queried fields
- Paginate large result sets

## Security Architecture

### Defense in Depth
- Multiple layers of security
- Validate at every boundary
- Never trust client input
- Use principle of least privilege

### Authentication & Authorization
- Separate authentication (who are you?) from authorization (what can you do?)
- Use established libraries for authentication
- Store permissions in central location
- Check permissions at service layer, not just UI

## Testing Architecture

### Test Pyramid
```
        /\
       /  \      E2E Tests (few)
      /────\
     /      \    Integration Tests (some)
    /────────\
   /          \  Unit Tests (many)
  /____________\
```

### Test Boundaries
- **Unit Tests** - Single function/class, mocked dependencies
- **Integration Tests** - Multiple modules, real dependencies
- **E2E Tests** - Full system, real environment

## Documentation Requirements

Document:
- Public APIs
- Complex business logic
- Architectural decisions (ADRs)
- Non-obvious behavior

Don't document:
- Self-explanatory code
- Implementation details that may change
- What the code does (code should be self-documenting)

## Language-Specific Guidelines

- **[Python](python/architecture.md)**
- **[Swift](swift/architecture.md)**
- **[Kotlin](kotlin/architecture.md)**

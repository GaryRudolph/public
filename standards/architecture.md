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

### Module Structure

```
feature/
├── index.ts              # Public API
├── types.ts              # Type definitions
├── service.ts            # Business logic
├── repository.ts         # Data access
├── validators.ts         # Input validation
└── __tests__/           # Tests
    ├── service.test.ts
    └── repository.test.ts
```

## Design Patterns

### Repository Pattern
Encapsulate data access logic

```typescript
interface UserRepository {
  findById(id: string): Promise<User | null>;
  findByEmail(email: string): Promise<User | null>;
  save(user: User): Promise<User>;
  delete(id: string): Promise<void>;
}

class DatabaseUserRepository implements UserRepository {
  async findById(id: string): Promise<User | null> {
    // Database-specific implementation
  }
  // ... other methods
}
```

### Service Layer Pattern
Encapsulate business logic

```typescript
class UserService {
  constructor(
    private userRepository: UserRepository,
    private emailService: EmailService
  ) {}

  async createUser(data: CreateUserData): Promise<User> {
    // 1. Validate
    this.validateUserData(data);

    // 2. Business logic
    const user = new User(data);

    // 3. Persist
    await this.userRepository.save(user);

    // 4. Side effects
    await this.emailService.sendWelcome(user);

    return user;
  }
}
```

### Factory Pattern
When object creation is complex

```typescript
class UserFactory {
  createFromApiResponse(data: ApiUser): User {
    return new User({
      id: data.user_id,
      email: data.email_address,
      createdAt: new Date(data.created_timestamp),
    });
  }
}
```

### Strategy Pattern
When you have multiple algorithms for the same task

```typescript
interface PaymentStrategy {
  processPayment(amount: number): Promise<PaymentResult>;
}

class CreditCardPayment implements PaymentStrategy {
  async processPayment(amount: number): Promise<PaymentResult> {
    // Credit card specific logic
  }
}

class PayPalPayment implements PaymentStrategy {
  async processPayment(amount: number): Promise<PaymentResult> {
    // PayPal specific logic
  }
}

class PaymentService {
  constructor(private strategy: PaymentStrategy) {}

  async pay(amount: number) {
    return this.strategy.processPayment(amount);
  }
}
```

## Dependency Management

### Dependency Injection
- Pass dependencies through constructors
- Makes code testable and flexible
- Avoid global state and singletons

```typescript
// Good - dependencies injected
class OrderService {
  constructor(
    private orderRepository: OrderRepository,
    private paymentService: PaymentService,
    private logger: Logger
  ) {}
}

// Avoid - hardcoded dependencies
class OrderService {
  private orderRepository = new OrderRepository();
  private paymentService = new PaymentService();
}
```

### Dependency Direction
- High-level modules should not depend on low-level modules
- Both should depend on abstractions (interfaces)

```typescript
// Business logic defines the interface it needs
interface EmailSender {
  send(to: string, subject: string, body: string): Promise<void>;
}

// Business logic depends on abstraction
class UserService {
  constructor(private emailSender: EmailSender) {}
}

// Infrastructure implements the interface
class SendGridEmailSender implements EmailSender {
  async send(to: string, subject: string, body: string): Promise<void> {
    // SendGrid specific implementation
  }
}
```

## Error Handling Architecture

### Error Hierarchy
```typescript
// Base error class
class AppError extends Error {
  constructor(
    message: string,
    public statusCode: number,
    public isOperational: boolean = true
  ) {
    super(message);
    this.name = this.constructor.name;
  }
}

// Specific error types
class ValidationError extends AppError {
  constructor(message: string) {
    super(message, 400);
  }
}

class NotFoundError extends AppError {
  constructor(resource: string) {
    super(`${resource} not found`, 404);
  }
}

class AuthenticationError extends AppError {
  constructor(message: string = 'Authentication failed') {
    super(message, 401);
  }
}
```

### Error Handling Layers
1. **Service Layer** - Throws domain-specific errors
2. **Controller Layer** - Catches and transforms to HTTP responses
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

### Avoid Global State
```typescript
// Avoid - global mutable state
let currentUser: User | null = null;

// Good - passed explicitly
function processOrder(order: Order, user: User) {
  // user is explicit parameter
}
```

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
```typescript
// Success response
{
  "data": { /* resource */ },
  "meta": { /* pagination, etc */ }
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

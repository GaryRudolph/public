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

**Good reasons:**
```typescript
// Cache results for 5 minutes to reduce API calls to rate-limited service
const CACHE_TTL = 5 * 60 * 1000;

// HACK: Temporary workaround for bug in library v2.3.1
// Remove when upgrading to v2.4.0
// See: https://github.com/library/issues/123
if (version === '2.3.1') {
  applyWorkaround();
}

// Using binary search for O(log n) performance on sorted array
const index = binarySearch(sortedArray, target);
```

**Bad reasons:**
```typescript
// Avoid - restates the code
// Set x to 5
const x = 5;

// Avoid - explains obvious code
// Loop through users
for (const user of users) {
  // Process user
  processUser(user);
}
```

### Comment Style

```typescript
// Single-line comments for brief explanations
const timeout = 30000; // 30 second timeout

/**
 * Multi-line comments for longer explanations.
 * Use this format for functions, classes, and complex logic.
 */
function complexFunction() {
  // Implementation
}
```

### TODO Comments
```typescript
// TODO: Add input validation
// TODO(username): Refactor to use new API
// TODO: [TICKET-123] Implement caching layer
// FIXME: This breaks when input is negative
// HACK: Workaround for Safari bug
// NOTE: This must run before initDatabase()
```

## Function Documentation

### JSDoc/TSDoc Format
```typescript
/**
 * Calculates the total price including tax and discount.
 *
 * @param items - Array of items with price and quantity
 * @param taxRate - Tax rate as decimal (e.g., 0.08 for 8%)
 * @param discountCode - Optional discount code to apply
 * @returns The total price after tax and discount
 * @throws {ValidationError} If items array is empty
 * @throws {InvalidDiscountError} If discount code is invalid
 *
 * @example
 * ```typescript
 * const total = calculateTotal(
 *   [{ price: 10, quantity: 2 }],
 *   0.08,
 *   'SAVE10'
 * );
 * console.log(total); // 19.44
 * ```
 */
function calculateTotal(
  items: Item[],
  taxRate: number,
  discountCode?: string
): number {
  // Implementation
}
```

### Python Docstrings
```python
def calculate_total(items: list[Item], tax_rate: float, discount_code: str = None) -> float:
    """
    Calculate the total price including tax and discount.

    Args:
        items: List of items with price and quantity
        tax_rate: Tax rate as decimal (e.g., 0.08 for 8%)
        discount_code: Optional discount code to apply

    Returns:
        The total price after tax and discount

    Raises:
        ValidationError: If items list is empty
        InvalidDiscountError: If discount code is invalid

    Example:
        >>> total = calculate_total([Item(price=10, quantity=2)], 0.08, 'SAVE10')
        >>> print(total)
        19.44
    """
    pass
```

## Class Documentation

```typescript
/**
 * Service for managing user accounts.
 *
 * Handles user creation, authentication, and profile management.
 * Uses UserRepository for data persistence and EmailService for notifications.
 *
 * @example
 * ```typescript
 * const userService = new UserService(userRepo, emailService);
 * const user = await userService.createUser({ email: 'user@example.com' });
 * ```
 */
class UserService {
  /**
   * Creates a new user account.
   *
   * Validates the user data, creates the account, and sends a welcome email.
   *
   * @param data - User creation data
   * @returns The created user
   * @throws {ValidationError} If user data is invalid
   * @throws {DuplicateEmailError} If email already exists
   */
  async createUser(data: CreateUserData): Promise<User> {
    // Implementation
  }
}
```

## Type Documentation

```typescript
/**
 * Configuration options for the API client.
 */
interface ApiConfig {
  /** Base URL for API requests */
  baseUrl: string;

  /** API key for authentication */
  apiKey: string;

  /** Request timeout in milliseconds */
  timeout?: number;

  /** Number of retry attempts for failed requests */
  retryAttempts?: number;
}

/**
 * Result of a payment transaction.
 */
type PaymentResult = {
  /** Whether the payment was successful */
  success: boolean;

  /** Transaction ID from payment provider */
  transactionId: string;

  /** Error message if payment failed */
  error?: string;
};
```

## README Files

### Project README Structure
```markdown
# Project Name

Brief description of what the project does.

## Features

- Key feature 1
- Key feature 2
- Key feature 3

## Installation

```bash
npm install
npm run setup
```

## Quick Start

```typescript
import { Feature } from 'project';

const feature = new Feature();
feature.doSomething();
```

## Configuration

Describe configuration options and environment variables.

## Usage

Detailed usage examples and common scenarios.

## API Documentation

Link to detailed API docs or include key endpoints.

## Development

How to set up development environment and run tests.

```bash
npm run dev
npm test
```

## Contributing

Guidelines for contributing to the project.

## License

License information.
```

### Module README
For complex modules within a project:

```markdown
# Module Name

What this module does and why it exists.

## Structure

```
module/
├── index.ts          # Public API
├── service.ts        # Main service logic
├── repository.ts     # Data access
└── types.ts          # Type definitions
```

## Usage

```typescript
import { ModuleService } from './module';

const service = new ModuleService();
const result = await service.doSomething();
```

## Architecture

Explain key architectural decisions and patterns used.

## Testing

How to run tests for this module specifically.
```

## API Documentation

### REST API Documentation
```markdown
## Endpoints

### GET /api/users/:id

Get user by ID.

**Parameters:**
- `id` (path, required) - User ID

**Response:** `200 OK`
```json
{
  "id": "123",
  "email": "user@example.com",
  "name": "John Doe"
}
```

**Errors:**
- `404 Not Found` - User not found
- `401 Unauthorized` - Authentication required

**Example:**
```bash
curl -H "Authorization: Bearer token" \
  https://api.example.com/api/users/123
```
```

### GraphQL Documentation
Use schema descriptions:

```graphql
"""
A user account in the system.
"""
type User {
  """Unique identifier for the user"""
  id: ID!

  """User's email address (unique)"""
  email: String!

  """User's display name"""
  name: String!
}

"""
Creates a new user account.
"""
createUser(
  """User registration data"""
  input: CreateUserInput!
): User!
```

## Architecture Decision Records (ADRs)

Document significant architectural decisions:

```markdown
# ADR-001: Use PostgreSQL for Primary Database

## Status
Accepted

## Context
We need to choose a database for our application. Requirements:
- ACID compliance
- Complex queries with joins
- Strong consistency
- Mature ecosystem

## Decision
We will use PostgreSQL as our primary database.

## Consequences

### Positive
- Strong ACID guarantees
- Excellent query optimizer
- Rich feature set (JSON, full-text search, etc.)
- Large community and ecosystem

### Negative
- More complex to scale horizontally than NoSQL
- Requires more resources than simpler databases
- Learning curve for advanced features

## Alternatives Considered
- MongoDB: Less suitable for relational data
- MySQL: Less feature-rich than PostgreSQL
```

## Changelog

### Format (Keep a Changelog)
```markdown
# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- New feature description

### Changed
- Change description

### Deprecated
- Deprecation notice

### Removed
- Removal description

### Fixed
- Bug fix description

### Security
- Security improvement description

## [1.1.0] - 2024-01-15

### Added
- User authentication system
- Email verification

### Fixed
- Memory leak in background job processor

## [1.0.0] - 2024-01-01

### Added
- Initial release
- Core API functionality
- Basic user management
```

## Inline Documentation

### Complex Algorithms
```typescript
/**
 * Implements the A* pathfinding algorithm.
 *
 * Time complexity: O(b^d) where b is branching factor and d is depth
 * Space complexity: O(b^d)
 *
 * Algorithm:
 * 1. Add start node to open set
 * 2. While open set not empty:
 *    a. Get node with lowest f-score
 *    b. If node is goal, reconstruct path
 *    c. Add node to closed set
 *    d. For each neighbor:
 *       - Calculate tentative g-score
 *       - If better than recorded, update and add to open set
 */
function findPath(start: Node, goal: Node): Node[] {
  // Implementation
}
```

### Magic Numbers
```typescript
// Avoid
const result = value * 1.08;

// Good - explain the number
const TAX_RATE = 1.08; // 8% sales tax
const result = value * TAX_RATE;
```

## Documentation Tools

### Recommended Tools
- **JSDoc/TSDoc** - JavaScript/TypeScript documentation
- **Sphinx** - Python documentation
- **Swagger/OpenAPI** - REST API documentation
- **GraphQL Playground** - GraphQL API documentation
- **Docusaurus** - Documentation websites
- **Storybook** - Component documentation

### Generating Documentation
```bash
# JavaScript/TypeScript
npx typedoc src/

# Python
sphinx-build -b html docs/ docs/_build

# OpenAPI
npx @redocly/cli build-docs openapi.yaml
```

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

### Be Concise
```typescript
// Verbose
/**
 * This function takes a user object as a parameter and then
 * validates all of the fields in the user object to make sure
 * they meet the requirements and then returns a boolean value
 * indicating whether the user object is valid or not.
 */

// Concise
/**
 * Validates user data against requirements.
 * @returns true if user is valid, false otherwise
 */
```

### Use Examples
```typescript
/**
 * Formats a date string.
 *
 * @example
 * formatDate('2024-01-01') // Returns: "January 1, 2024"
 * formatDate('2024-01-01', 'short') // Returns: "Jan 1, 2024"
 */
```

### Keep It Updated
- Remove documentation for deleted code
- Update documentation when behavior changes
- Mark deprecated features clearly

### Link to Resources
```typescript
/**
 * Implements OAuth 2.0 authorization code flow.
 *
 * See: https://tools.ietf.org/html/rfc6749#section-4.1
 */
```

## Accessibility

- Use descriptive link text
- Include alt text for images
- Use semantic HTML in markdown
- Ensure good contrast in code examples
- Test with screen readers when applicable

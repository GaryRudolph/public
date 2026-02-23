# Testing Standards

## Testing Philosophy

- **Write tests first** - Consider TDD for complex logic
- **Test behavior, not implementation** - Tests should survive refactoring
- **Fast feedback** - Tests should run quickly
- **Independent tests** - Tests should not depend on each other
- **Clear failures** - When tests fail, it should be obvious why

## Test Coverage

### Minimum Requirements
- **Unit Tests**: 80% code coverage for business logic
- **Integration Tests**: All critical user paths
- **E2E Tests**: Core user flows and happy paths

### What to Test
**Always test:**
- Business logic and calculations
- Data transformations
- Edge cases and error conditions
- Public APIs and interfaces
- Security-critical code

**Don't test:**
- Third-party library internals
- Simple getters/setters without logic
- Framework boilerplate

## Test Structure

### Test Organization
```
src/
├── feature/
│   ├── service.ts
│   └── __tests__/
│       ├── service.test.ts
│       └── service.integration.test.ts
└── tests/
    ├── unit/           # Additional unit tests
    ├── integration/    # Integration tests
    └── e2e/           # End-to-end tests
```

### Test Naming
Use descriptive names that explain the scenario:

```typescript
// Good - describes behavior
describe('UserService', () => {
  describe('createUser', () => {
    it('should create user with valid data', () => {});
    it('should throw ValidationError when email is invalid', () => {});
    it('should send welcome email after user creation', () => {});
  });
});

// Avoid - vague names
describe('UserService', () => {
  it('test1', () => {});
  it('works', () => {});
});
```

### AAA Pattern (Arrange, Act, Assert)
```typescript
it('should calculate total with discount', () => {
  // Arrange - Setup test data
  const items = [
    { price: 10, quantity: 2 },
    { price: 5, quantity: 1 },
  ];
  const discount = 0.1;

  // Act - Execute the code under test
  const total = calculateTotal(items, discount);

  // Assert - Verify the result
  expect(total).toBe(22.5); // (10*2 + 5*1) * 0.9
});
```

## Unit Testing

### Principles
- Test one thing at a time
- Mock external dependencies
- Fast execution (< 100ms per test)
- No network or file system access

### Example
```typescript
describe('OrderService', () => {
  let orderService: OrderService;
  let mockOrderRepository: jest.Mocked<OrderRepository>;
  let mockPaymentService: jest.Mocked<PaymentService>;

  beforeEach(() => {
    // Arrange - Create mocks
    mockOrderRepository = {
      save: jest.fn(),
      findById: jest.fn(),
    } as any;

    mockPaymentService = {
      processPayment: jest.fn(),
    } as any;

    orderService = new OrderService(
      mockOrderRepository,
      mockPaymentService
    );
  });

  describe('createOrder', () => {
    it('should create order and process payment', async () => {
      // Arrange
      const orderData = { items: [{ id: '1', quantity: 2 }] };
      mockPaymentService.processPayment.mockResolvedValue({ success: true });
      mockOrderRepository.save.mockResolvedValue({ id: 'order-1', ...orderData });

      // Act
      const result = await orderService.createOrder(orderData);

      // Assert
      expect(mockPaymentService.processPayment).toHaveBeenCalledWith(
        expect.objectContaining({ amount: expect.any(Number) })
      );
      expect(mockOrderRepository.save).toHaveBeenCalledTimes(1);
      expect(result).toHaveProperty('id', 'order-1');
    });

    it('should rollback order if payment fails', async () => {
      // Arrange
      const orderData = { items: [{ id: '1', quantity: 2 }] };
      mockPaymentService.processPayment.mockRejectedValue(
        new Error('Payment failed')
      );

      // Act & Assert
      await expect(orderService.createOrder(orderData)).rejects.toThrow('Payment failed');
      expect(mockOrderRepository.save).not.toHaveBeenCalled();
    });
  });
});
```

## Integration Testing

### Purpose
- Test interaction between modules
- Use real dependencies where practical
- Test database operations, API calls

### Database Tests
```typescript
describe('UserRepository Integration', () => {
  let db: Database;
  let userRepository: UserRepository;

  beforeAll(async () => {
    // Setup test database
    db = await createTestDatabase();
    userRepository = new UserRepository(db);
  });

  beforeEach(async () => {
    // Clean database before each test
    await db.query('TRUNCATE users CASCADE');
  });

  afterAll(async () => {
    // Cleanup
    await db.close();
  });

  it('should save and retrieve user', async () => {
    // Arrange
    const user = { email: 'test@example.com', name: 'Test User' };

    // Act
    const saved = await userRepository.save(user);
    const retrieved = await userRepository.findById(saved.id);

    // Assert
    expect(retrieved).toMatchObject(user);
  });

  it('should throw error when saving duplicate email', async () => {
    // Arrange
    const user = { email: 'test@example.com', name: 'Test User' };
    await userRepository.save(user);

    // Act & Assert
    await expect(userRepository.save(user)).rejects.toThrow('Email already exists');
  });
});
```

## End-to-End Testing

### Purpose
- Test complete user workflows
- Use real environment (or close to it)
- Fewer tests, higher confidence

### Example
```typescript
describe('User Registration Flow', () => {
  let browser: Browser;
  let page: Page;

  beforeAll(async () => {
    browser = await puppeteer.launch();
  });

  beforeEach(async () => {
    page = await browser.newPage();
    await page.goto('http://localhost:3000/register');
  });

  afterEach(async () => {
    await page.close();
  });

  afterAll(async () => {
    await browser.close();
  });

  it('should register new user successfully', async () => {
    // Arrange & Act
    await page.type('#email', 'newuser@example.com');
    await page.type('#password', 'SecurePass123!');
    await page.type('#confirmPassword', 'SecurePass123!');
    await page.click('button[type="submit"]');

    // Wait for redirect
    await page.waitForNavigation();

    // Assert
    const url = page.url();
    expect(url).toContain('/dashboard');

    const welcomeMessage = await page.$eval('.welcome', el => el.textContent);
    expect(welcomeMessage).toContain('Welcome');
  });

  it('should show error for invalid email', async () => {
    // Act
    await page.type('#email', 'invalid-email');
    await page.type('#password', 'SecurePass123!');
    await page.click('button[type="submit"]');

    // Assert
    const error = await page.$eval('.error', el => el.textContent);
    expect(error).toContain('Invalid email');
  });
});
```

## Test Data Management

### Test Fixtures
```typescript
// test/fixtures/users.ts
export const validUser = {
  email: 'user@example.com',
  name: 'Test User',
  role: 'user',
};

export const adminUser = {
  email: 'admin@example.com',
  name: 'Admin User',
  role: 'admin',
};

// Usage
import { validUser } from './fixtures/users';

it('should create user', async () => {
  const result = await userService.createUser(validUser);
  expect(result.email).toBe(validUser.email);
});
```

### Factory Functions
```typescript
// test/factories/user.factory.ts
let userIdCounter = 0;

export function createUser(overrides: Partial<User> = {}): User {
  return {
    id: `user-${++userIdCounter}`,
    email: `user${userIdCounter}@example.com`,
    name: 'Test User',
    createdAt: new Date(),
    ...overrides,
  };
}

// Usage
const user1 = createUser({ email: 'specific@example.com' });
const user2 = createUser(); // Gets auto-generated email
```

## Mocking Best Practices

### When to Mock
- External APIs
- Slow operations (database, file system)
- Non-deterministic behavior (dates, random)
- Third-party services

### When Not to Mock
- Simple pure functions
- Code under test
- Internal business logic

### Mock Examples
```typescript
// Mock external API
jest.mock('./api/github', () => ({
  fetchUser: jest.fn().mockResolvedValue({
    id: '123',
    name: 'Test User',
  }),
}));

// Mock date
const mockDate = new Date('2024-01-01');
jest.spyOn(global, 'Date').mockImplementation(() => mockDate);

// Mock module
jest.mock('./config', () => ({
  API_KEY: 'test-key',
  API_URL: 'http://test-api.com',
}));
```

## Testing Async Code

### Promises
```typescript
it('should fetch user data', async () => {
  const user = await userService.getUser('123');
  expect(user).toBeDefined();
});

// Alternative
it('should fetch user data', () => {
  return userService.getUser('123').then(user => {
    expect(user).toBeDefined();
  });
});
```

### Error Handling
```typescript
it('should throw error for invalid id', async () => {
  await expect(userService.getUser('invalid')).rejects.toThrow('User not found');
});
```

## Test Assertions

### Use Specific Matchers
```typescript
// Good - specific matchers
expect(value).toBe(5);
expect(array).toHaveLength(3);
expect(string).toContain('substring');
expect(object).toHaveProperty('name', 'John');
expect(fn).toHaveBeenCalledWith(arg1, arg2);

// Avoid - vague assertions
expect(value > 0).toBe(true);
expect(!!value).toBe(true);
```

### Custom Matchers
```typescript
expect.extend({
  toBeValidEmail(received: string) {
    const pass = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(received);
    return {
      pass,
      message: () => `expected ${received} to be a valid email`,
    };
  },
});

// Usage
expect('user@example.com').toBeValidEmail();
```

## Testing Anti-Patterns

### Don't Test Implementation Details
```typescript
// Avoid - testing internal state
it('should set internal flag', () => {
  const service = new UserService();
  service.someMethod();
  expect(service['internalFlag']).toBe(true); // Bad!
});

// Good - test behavior
it('should send notification after user creation', async () => {
  await userService.createUser(userData);
  expect(mockNotificationService.send).toHaveBeenCalled();
});
```

### Don't Write Brittle Tests
```typescript
// Avoid - too specific, breaks easily
expect(result).toEqual({
  id: '123',
  name: 'John',
  email: 'john@example.com',
  createdAt: '2024-01-01T00:00:00.000Z',
  updatedAt: '2024-01-01T00:00:00.000Z',
  version: 1,
});

// Good - test what matters
expect(result).toMatchObject({
  name: 'John',
  email: 'john@example.com',
});
expect(result.id).toBeDefined();
expect(result.createdAt).toBeInstanceOf(Date);
```

### Avoid Test Interdependence
```typescript
// Avoid - tests depend on execution order
let userId: string;

it('should create user', async () => {
  const user = await createUser();
  userId = user.id; // Shared state!
});

it('should update user', async () => {
  await updateUser(userId); // Depends on previous test
});

// Good - each test is independent
it('should create user', async () => {
  const user = await createUser();
  expect(user.id).toBeDefined();
});

it('should update user', async () => {
  const user = await createUser(); // Create own data
  const updated = await updateUser(user.id);
  expect(updated).toBeDefined();
});
```

## Performance Testing

### Test Execution Time
```typescript
it('should process large dataset efficiently', () => {
  const start = Date.now();
  const result = processLargeDataset(data);
  const duration = Date.now() - start;

  expect(duration).toBeLessThan(1000); // Should complete in < 1s
});
```

### Load Testing
- Use dedicated tools (k6, Artillery, JMeter)
- Test realistic scenarios
- Monitor system resources

## Continuous Testing

### Pre-commit Hooks
```bash
# Run tests before commit
npm test

# Run linting
npm run lint
```

### CI/CD Pipeline
```yaml
# Example: GitHub Actions
name: Test
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run unit tests
        run: npm run test:unit
      - name: Run integration tests
        run: npm run test:integration
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Test Documentation

Document:
- Complex test setup
- Non-obvious test scenarios
- Reasons for skipped tests
- Test environment requirements

```typescript
/**
 * Tests user authentication flow.
 *
 * Note: These tests require a test database to be running.
 * Run `npm run test:db:setup` before executing.
 */
describe('Authentication Integration Tests', () => {
  // tests...
});
```

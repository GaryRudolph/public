# Security Standards

## Security Principles

### Defense in Depth
- Multiple layers of security
- Assume any single layer can be breached
- Validate at every boundary

### Principle of Least Privilege
- Grant minimum necessary permissions
- Limit access duration
- Regular permission audits

### Secure by Default
- Safe defaults in configuration
- Require explicit opt-in for risky features
- Fail securely when errors occur

### Never Trust Input
- Validate all external input
- Sanitize and escape data
- Use parameterized queries
- Validate on server side, not just client

## Authentication & Authorization

### Password Security

**Requirements:**
```typescript
// Password policy
const PASSWORD_REQUIREMENTS = {
  minLength: 12,
  requireUppercase: true,
  requireLowercase: true,
  requireNumbers: true,
  requireSpecialChars: true,
  preventCommonPasswords: true,
  preventReuse: 5, // Don't reuse last 5 passwords
};
```

**Hashing:**
```typescript
// Good - use bcrypt with proper cost factor
import bcrypt from 'bcrypt';

const SALT_ROUNDS = 12; // Adjust based on performance/security tradeoff

async function hashPassword(password: string): Promise<string> {
  return bcrypt.hash(password, SALT_ROUNDS);
}

async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return bcrypt.compare(password, hash);
}

// Never do this
const hash = crypto.createHash('md5').update(password).digest('hex'); // Insecure!
```

### Token Security

```typescript
// JWT best practices
const token = jwt.sign(
  { userId: user.id, role: user.role }, // Minimal payload
  process.env.JWT_SECRET,
  {
    expiresIn: '15m', // Short expiration
    algorithm: 'HS256',
    issuer: 'your-app',
    audience: 'your-app-api',
  }
);

// Refresh tokens
const refreshToken = generateSecureRandomToken();
await storeRefreshToken(userId, refreshToken, {
  expiresAt: Date.now() + 7 * 24 * 60 * 60 * 1000, // 7 days
  rotateOnUse: true,
});
```

### Session Management

```typescript
// Secure session configuration
app.use(session({
  secret: process.env.SESSION_SECRET, // Long random string
  name: 'sessionId', // Don't use default name
  resave: false,
  saveUninitialized: false,
  cookie: {
    secure: true, // HTTPS only
    httpOnly: true, // No JavaScript access
    maxAge: 15 * 60 * 1000, // 15 minutes
    sameSite: 'strict', // CSRF protection
  },
}));
```

### Multi-Factor Authentication

```typescript
// Implement MFA for sensitive operations
interface MFAConfig {
  required: boolean;
  methods: ['totp', 'sms', 'email'];
  backupCodes: number; // Number of backup codes
}

// TOTP (Time-based One-Time Password)
import speakeasy from 'speakeasy';

const secret = speakeasy.generateSecret({
  name: 'YourApp (user@example.com)',
  length: 32,
});

const verified = speakeasy.totp.verify({
  secret: secret.base32,
  encoding: 'base32',
  token: userEnteredCode,
  window: 1, // Allow 1 step before/after
});
```

## Input Validation

### Validation Rules

```typescript
// Always validate input
import { z } from 'zod';

const CreateUserSchema = z.object({
  email: z.string().email().max(255),
  password: z.string().min(12).max(128),
  name: z.string().min(1).max(100).regex(/^[a-zA-Z\s'-]+$/),
  age: z.number().int().min(0).max(150),
});

function createUser(input: unknown) {
  // Validate before processing
  const data = CreateUserSchema.parse(input);
  // ... proceed with validated data
}
```

### Sanitization

```typescript
// HTML sanitization
import DOMPurify from 'isomorphic-dompurify';

function sanitizeHtml(dirty: string): string {
  return DOMPurify.sanitize(dirty, {
    ALLOWED_TAGS: ['b', 'i', 'em', 'strong', 'p', 'br'],
    ALLOWED_ATTR: [],
  });
}

// SQL injection prevention - use parameterized queries
// Good
const users = await db.query(
  'SELECT * FROM users WHERE email = $1',
  [email]
);

// Never do this
const users = await db.query(
  `SELECT * FROM users WHERE email = '${email}'` // SQL injection!
);
```

### File Upload Security

```typescript
// Secure file upload handling
const ALLOWED_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif'];
const MAX_FILE_SIZE = 5 * 1024 * 1024; // 5MB

function validateUpload(file: UploadedFile) {
  // Check file size
  if (file.size > MAX_FILE_SIZE) {
    throw new Error('File too large');
  }

  // Check MIME type
  if (!ALLOWED_MIME_TYPES.includes(file.mimetype)) {
    throw new Error('Invalid file type');
  }

  // Verify file content matches extension
  const actualType = await detectFileType(file.buffer);
  if (actualType !== file.mimetype) {
    throw new Error('File type mismatch');
  }

  // Generate safe filename
  const safeFilename = `${uuid()}.${getExtension(file.mimetype)}`;

  return { safeFilename, file };
}
```

## Cross-Site Scripting (XSS) Prevention

### Output Encoding

```typescript
// React automatically escapes (safe)
<div>{userInput}</div>

// Be careful with dangerouslySetInnerHTML
<div dangerouslySetInnerHTML={{ __html: sanitizeHtml(userInput) }} />

// Template literals - manually escape
function escapeHtml(unsafe: string): string {
  return unsafe
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
```

### Content Security Policy

```typescript
// Set CSP headers
app.use((req, res, next) => {
  res.setHeader(
    'Content-Security-Policy',
    "default-src 'self'; " +
    "script-src 'self' 'unsafe-inline' https://trusted-cdn.com; " +
    "style-src 'self' 'unsafe-inline'; " +
    "img-src 'self' data: https:; " +
    "font-src 'self'; " +
    "connect-src 'self' https://api.yourapp.com; " +
    "frame-ancestors 'none';"
  );
  next();
});
```

## Cross-Site Request Forgery (CSRF) Prevention

```typescript
// Use CSRF tokens
import csrf from 'csurf';

app.use(csrf({ cookie: true }));

// Include token in forms
app.get('/form', (req, res) => {
  res.render('form', { csrfToken: req.csrfToken() });
});

// Verify token on submission
app.post('/submit', (req, res) => {
  // Token automatically verified by middleware
});

// For APIs, use double-submit cookie pattern or custom headers
app.use((req, res, next) => {
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    const token = req.headers['x-csrf-token'];
    const cookieToken = req.cookies.csrfToken;

    if (token !== cookieToken) {
      return res.status(403).json({ error: 'Invalid CSRF token' });
    }
  }
  next();
});
```

## API Security

### Rate Limiting

```typescript
import rateLimit from 'express-rate-limit';

// General rate limiting
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100, // Limit each IP to 100 requests per windowMs
  message: 'Too many requests, please try again later',
  standardHeaders: true,
  legacyHeaders: false,
});

// Stricter for authentication endpoints
const authLimiter = rateLimit({
  windowMs: 15 * 60 * 1000,
  max: 5, // Only 5 attempts per 15 minutes
  skipSuccessfulRequests: true,
});

app.use('/api/', limiter);
app.use('/api/auth/', authLimiter);
```

### API Key Security

```typescript
// Store API keys securely
interface ApiKey {
  id: string;
  userId: string;
  keyHash: string; // Store hash, not plain key
  name: string;
  permissions: string[];
  expiresAt: Date;
  lastUsed: Date;
}

// Generate secure API keys
function generateApiKey(): string {
  return `app_${crypto.randomBytes(32).toString('base64url')}`;
}

// Validate API key
async function validateApiKey(key: string): Promise<ApiKey | null> {
  const keyHash = hashApiKey(key);
  const apiKey = await db.findByHash(keyHash);

  if (!apiKey || apiKey.expiresAt < new Date()) {
    return null;
  }

  // Update last used
  await db.updateLastUsed(apiKey.id);

  return apiKey;
}
```

## Database Security

### SQL Injection Prevention

```typescript
// Always use parameterized queries
// Good
const user = await db.query(
  'SELECT * FROM users WHERE email = $1 AND role = $2',
  [email, role]
);

// Good - ORM
const user = await User.findOne({
  where: { email, role },
});

// Never concatenate SQL
// Bad
const user = await db.query(
  `SELECT * FROM users WHERE email = '${email}'` // Vulnerable!
);
```

### Least Privilege

```sql
-- Create application user with minimal permissions
CREATE USER app_user WITH PASSWORD 'secure_password';

-- Grant only necessary permissions
GRANT SELECT, INSERT, UPDATE ON users TO app_user;
GRANT SELECT ON products TO app_user;

-- Don't grant DROP, DELETE on production tables
-- Don't use root/admin accounts for applications
```

## Secrets Management

### Environment Variables

```typescript
// .env file (never commit!)
DATABASE_URL=postgresql://user:pass@localhost/db
JWT_SECRET=your-very-long-random-secret-here
API_KEY=your-api-key-here

// Load securely
import dotenv from 'dotenv';
dotenv.config();

// Validate required secrets exist
const requiredEnvVars = ['DATABASE_URL', 'JWT_SECRET', 'API_KEY'];
for (const varName of requiredEnvVars) {
  if (!process.env[varName]) {
    throw new Error(`Missing required environment variable: ${varName}`);
  }
}

// Never log secrets
console.log(`Using database: ${process.env.DATABASE_URL}`); // Bad!
console.log('Database configured'); // Good
```

### Secret Rotation

```typescript
// Support multiple active keys for rotation
const JWT_SECRETS = [
  process.env.JWT_SECRET_CURRENT,
  process.env.JWT_SECRET_PREVIOUS,
];

function verifyToken(token: string): TokenPayload {
  let lastError: Error;

  // Try each secret
  for (const secret of JWT_SECRETS) {
    try {
      return jwt.verify(token, secret);
    } catch (err) {
      lastError = err;
    }
  }

  throw lastError;
}
```

## Encryption

### Data at Rest

```typescript
// Encrypt sensitive data before storing
import crypto from 'crypto';

const ALGORITHM = 'aes-256-gcm';
const KEY = Buffer.from(process.env.ENCRYPTION_KEY, 'hex'); // 32 bytes

function encrypt(text: string): { encrypted: string; iv: string; tag: string } {
  const iv = crypto.randomBytes(16);
  const cipher = crypto.createCipheriv(ALGORITHM, KEY, iv);

  let encrypted = cipher.update(text, 'utf8', 'hex');
  encrypted += cipher.final('hex');

  return {
    encrypted,
    iv: iv.toString('hex'),
    tag: cipher.getAuthTag().toString('hex'),
  };
}

function decrypt(encrypted: string, iv: string, tag: string): string {
  const decipher = crypto.createDecipheriv(
    ALGORITHM,
    KEY,
    Buffer.from(iv, 'hex')
  );

  decipher.setAuthTag(Buffer.from(tag, 'hex'));

  let decrypted = decipher.update(encrypted, 'hex', 'utf8');
  decrypted += decipher.final('utf8');

  return decrypted;
}
```

### Data in Transit

```typescript
// Always use HTTPS
// Redirect HTTP to HTTPS
app.use((req, res, next) => {
  if (!req.secure && process.env.NODE_ENV === 'production') {
    return res.redirect('https://' + req.headers.host + req.url);
  }
  next();
});

// Set security headers
app.use((req, res, next) => {
  res.setHeader('Strict-Transport-Security', 'max-age=31536000; includeSubDomains');
  res.setHeader('X-Content-Type-Options', 'nosniff');
  res.setHeader('X-Frame-Options', 'DENY');
  res.setHeader('X-XSS-Protection', '1; mode=block');
  next();
});
```

## Logging & Monitoring

### Security Logging

```typescript
// Log security events
interface SecurityEvent {
  type: 'login' | 'logout' | 'failed_login' | 'permission_denied' | 'suspicious_activity';
  userId?: string;
  ip: string;
  userAgent: string;
  timestamp: Date;
  details: Record<string, any>;
}

function logSecurityEvent(event: SecurityEvent) {
  // Never log sensitive data
  const sanitized = {
    ...event,
    details: {
      ...event.details,
      password: undefined,
      token: undefined,
      apiKey: undefined,
    },
  };

  logger.security(sanitized);

  // Alert on suspicious patterns
  if (shouldAlert(event)) {
    alertSecurityTeam(event);
  }
}

// Monitor failed login attempts
const failedAttempts = new Map<string, number>();

function trackFailedLogin(ip: string) {
  const attempts = (failedAttempts.get(ip) || 0) + 1;
  failedAttempts.set(ip, attempts);

  if (attempts > 5) {
    logSecurityEvent({
      type: 'suspicious_activity',
      ip,
      userAgent: req.headers['user-agent'],
      timestamp: new Date(),
      details: { failedAttempts: attempts },
    });

    // Implement temporary IP ban
    banIP(ip, 15 * 60 * 1000); // 15 minutes
  }
}
```

## Security Headers

```typescript
// Use helmet.js for security headers
import helmet from 'helmet';

app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'"],
      scriptSrc: ["'self'"],
      imgSrc: ["'self'", 'data:', 'https:'],
    },
  },
  hsts: {
    maxAge: 31536000,
    includeSubDomains: true,
    preload: true,
  },
}));
```

## Dependency Security

### Regular Updates

```bash
# Check for vulnerabilities
npm audit

# Fix automatically
npm audit fix

# Use dependabot or renovate for automated updates
```

### Supply Chain Security

```bash
# Verify package integrity
npm install --package-lock-only

# Use lock files
# Commit package-lock.json or yarn.lock

# Review dependencies before adding
npm view package-name
```

## Security Checklist

### Before Deployment
- [ ] All secrets in environment variables
- [ ] HTTPS enforced
- [ ] Security headers configured
- [ ] Rate limiting implemented
- [ ] Input validation on all endpoints
- [ ] SQL injection prevention (parameterized queries)
- [ ] XSS prevention (output encoding)
- [ ] CSRF protection enabled
- [ ] Authentication & authorization implemented
- [ ] Passwords properly hashed
- [ ] Dependencies updated and audited
- [ ] Error messages don't leak sensitive info
- [ ] Logging configured (excluding sensitive data)
- [ ] Security testing completed

### Regular Security Tasks
- [ ] Rotate secrets and API keys
- [ ] Review access logs for suspicious activity
- [ ] Update dependencies
- [ ] Run security scans
- [ ] Review and update permissions
- [ ] Test backup and recovery procedures
- [ ] Review security incidents and learnings

## Common Vulnerabilities

### OWASP Top 10
1. **Broken Access Control** - Enforce authorization checks
2. **Cryptographic Failures** - Use strong encryption, secure storage
3. **Injection** - Validate and sanitize input, use parameterized queries
4. **Insecure Design** - Security by design, threat modeling
5. **Security Misconfiguration** - Secure defaults, regular updates
6. **Vulnerable Components** - Keep dependencies updated
7. **Authentication Failures** - Strong passwords, MFA, secure sessions
8. **Data Integrity Failures** - Verify data integrity, use signed updates
9. **Logging Failures** - Log security events, monitor for anomalies
10. **Server-Side Request Forgery** - Validate URLs, whitelist destinations

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [Security Headers](https://securityheaders.com/)

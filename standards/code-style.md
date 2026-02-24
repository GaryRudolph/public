# Code Style Standards

## General Principles

- **Readability over cleverness** - Write code that is easy to understand
- **Consistency** - Follow existing patterns in the codebase
- **Simplicity** - Avoid unnecessary complexity
- **Self-documenting** - Use clear names and structure

## Naming Conventions

### Variables and Functions
- Use **descriptive, pronounceable names**
- Avoid abbreviations unless widely understood
- Use **PascalCase** for classes and types
- Prefix booleans with `is`, `has`, `can`, `should`; make the positive case clear

### Files and Directories
- Use **singular names** for single-entity files
- Use **plural names** for collections: `utils/`, `helpers/`
- Match file name to primary export (e.g. `UserService` class lives in a file named `UserService`)
- Prefer a file and directory structure where files that work together are stored together (e.g. `src/user/`)
- Prefer data logic and business logic in the same directory structure with nesting (e.g. `src/user/data` and `src/user/service`)
- Prefer separate projects for clean separation between services and UI

## Formatting

### Indentation
- Use the language community's standard indentation (typically 4 spaces)
- No tabs
- See language-specific guides for exact settings

### Line Length
- Keep lines short enough to read without horizontal scrolling (typically 80-120 characters)
- Break long lines at logical boundaries
- See language-specific guides for exact limits (Python: 88, Swift: 120, Kotlin: 100)

## Comments
- Use comments to explain **why**, not what
- Place comments above the code they describe
- Keep comments up-to-date with code changes

## File Headers

For open-source libraries and packages, include a consistent copyright and license header at the top of every source file. Place it before imports. Use the language's comment syntax (see language-specific guides for exact format).

For private/internal projects, a shorter header (just copyright) or no header is acceptable if the codebase doesn't use them. Be consistent within a repository.

## Imports

### Ordering
1. Standard library imports
2. Third-party imports
3. Local application imports

### Avoid Circular Dependencies
- Keep module dependencies unidirectional
- Extract shared code to separate modules

## Anti-Patterns to Avoid

### Large Functions
- Keep functions small and focused
- Extract complex logic into separate functions
- Aim for < 50 lines per function

## Tools

Configure your editor to:
- Format on save
- Show linting errors
- Auto-fix common issues
- Highlight trailing whitespace

## Language-Specific Guidelines

- **[Python](python/code-style.md)**
- **[Swift](swift/code-style.md)**
- **[Kotlin](kotlin/code-style.md)**

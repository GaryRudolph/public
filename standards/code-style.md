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
- Use **singular names** for single-entity files: `user_model.py`, `UserModel.swift`
- Use **plural names** for collections: `utils/`, `helpers/`
- Match file name to primary export: `UserService` class in `user_service.py` or `UserService.swift`
- Prefer a file and directory structure where files that work together are stored together (e.g. `src/user/`)
- Prefer data logic and business logic in the same directory structure with nesting (e.g. `src/user/data` and `src/user/service`)
- Prefer separate projects for clean separation between services and UI

## Formatting

### Indentation
- Use **2 spaces** for indentation (or 4 spaces, but be consistent)
- No tabs

### Line Length
- Maximum **100 characters** per line
- Break long lines at logical boundaries

## Comments
- Use comments to explain **why**, not what
- Place comments above the code they describe
- Keep comments up-to-date with code changes

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

- **[Python](code-style-python.md)**
- **[Swift](code-style-swift.md)**

# Code Style Standards

## General Principles

- **Readability over cleverness** — write code that is easy to understand
- **Consistency** — follow existing patterns in the codebase
- **Simplicity** — avoid unnecessary complexity
- **Self-documenting** — use clear names and structure

## Naming Conventions

- Use **descriptive, pronounceable names**; avoid abbreviations unless widely understood
- Use **PascalCase** for classes and types
- Prefix booleans with `is`, `has`, `can`, `should`; make the positive case clear
- **Singular names** for single-entity files; **plural names** for collections: `utils/`, `helpers/`
- Match file name to primary export (e.g. `UserService` class in `UserService` file)
- Colocate related files (e.g. `src/user/data` and `src/user/service`)
- Prefer separate projects for clean separation between services and UI

## Formatting

- Use the language community's standard indentation (typically 4 spaces); no tabs
- Line length: 80-120 characters; see language-specific guides (Python: 88, Swift: 120, Kotlin: 100)
- Comments explain **why**, not what; keep comments up-to-date

## File Headers

For open-source packages: consistent copyright and license header at top of every source file, before imports. For private projects: shorter header or none — be consistent within a repo.

## Imports

1. Standard library
2. Third-party
3. Local application

Keep module dependencies unidirectional; extract shared code to separate modules.

## Anti-Patterns

- **Large functions**: keep < 50 lines; extract complex logic
- **Magic numbers**: use named constants
- **Deep nesting**: use early returns/guards

## Language-Specific Guidelines

- **[Python](python/code-style.md)**
- **[Swift](swift/code-style.md)**
- **[Kotlin](kotlin/code-style.md)**

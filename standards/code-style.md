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
- **Python**: 4 spaces (per PEP 8)
- **Swift**: 4 spaces
- No tabs

### Line Length
- Maximum **100 characters** per line
- Break long lines at logical boundaries

## Comments
- Use comments to explain **why**, not what
- Place comments above the code they describe
- Keep comments up-to-date with code changes

## File Headers

For open-source libraries and packages, include a consistent copyright and license header at the top of every source file. Place it before imports:

**Swift:**
```swift
//  Copyright © 2024 Company, Inc.
//
//  Licensed under the Apache License, Version 2.0 (the "License");
//  you may not use this file except in compliance with the License.
//  You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
//  Unless required by applicable law or agreed to in writing, software
//  distributed under the License is distributed on an "AS IS" BASIS,
//  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
//  See the License for the specific language governing permissions and
//  limitations under the License.
//

import Foundation
```

**Python:**
```python
# Copyright © 2024 Company, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# ...

from __future__ import annotations
```

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

- **[Python](code-style-python.md)**
- **[Swift](code-style-swift.md)**
- **[Kotlin](code-style-kotlin.md)**

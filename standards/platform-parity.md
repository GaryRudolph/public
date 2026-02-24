# Cross-Platform Architectural Parity

When a product ships native iOS (Swift) and Android (Kotlin) apps, the two codebases should use parallel architecture, directory structure, and naming. An engineer editing `LoginViewModel` in Swift should find `LoginViewModel` in Kotlin without searching. Each codebase remains idiomatic to its platform, but the high-level design is intentionally mirrored.

## Naming Parity

| Concept | Convention |
|---|---|
| Feature modules | Same name on both platforms: `Login/`, `Inventory/`, `Settings/` |
| ViewModels | Same class name: `LoginViewModel`, `TicketsViewModel` |
| Repositories | Same class name: `UserRepository`, `OrderRepository` |
| Domain models | Same name, no platform suffix: `Account`, `Ticket`, `Order` |
| DI wiring | Parallel concept — mechanism differs (manual factory vs Hilt) but dependency graph mirrors |

## Layer Parity

Both platforms use the same logical layers with the same names:

| Layer | Swift | Kotlin |
|---|---|---|
| Presentation | SwiftUI Views + `@ObservableObject` ViewModels | Compose screens + MVI ViewModels |
| Business Logic | Manager protocols + `Impl` classes | Use-case / service classes |
| Data | Repositories, network clients | Repositories, network clients |
| Navigation | Router pattern (`NavigationRouter`) | Navigation component / router |

## Platform Concept Mapping

Use the platform-native idiom, not a literal translation:

| Concept | Swift | Kotlin |
|---|---|---|
| Reactive state | `@Published` / `ObservableObject` | `StateFlow` / `MutableStateFlow` |
| Main-thread binding | `@MainActor` | `Dispatchers.Main` / `viewModelScope` |
| Structured concurrency | `async`/`await`, `TaskGroup` | Coroutines, `CoroutineScope` |
| Sealed state types | `enum` with associated values | `sealed interface` / `sealed class` |
| Dependency injection | Constructor injection + `ManagerFactory` | Constructor injection + Hilt modules |
| Error modeling | `enum: Error` + `LocalizedError` | `sealed interface Result` / custom exceptions |
| Immutable collections | `let` + value types | `val` + `List` / `Map` (read-only interfaces) |

## Where Divergence Is Expected

Parity applies to architecture and naming, not platform mechanics. These remain fully idiomatic:

- UI framework specifics (SwiftUI modifiers vs Compose modifiers)
- Concurrency primitives (`Task` vs `launch`, `Actor` vs `Mutex`)
- DI mechanism (manual lazy factory vs Hilt annotation processing)
- Build system (SPM/Xcode vs Gradle)
- Platform APIs (HealthKit, WorkManager, etc.)
- File organization (Swift groups vs Kotlin packages)

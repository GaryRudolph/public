# Architecture — Kotlin

Follows [architecture.md](../architecture.md).

## MVI Pattern (Jetpack Compose)

Unidirectional data flow: ViewModel exposes single `StateFlow<UiState>`, UI sends `Event` objects:

```kotlin
sealed interface UiState {
    data object Loading : UiState
    data class Success(val items: List<Item>) : UiState
    data class Error(val message: String) : UiState
}

sealed interface UiEvent {
    data object Refresh : UiEvent
    data class ItemClicked(val id: String) : UiEvent
}

class ItemsViewModel(private val repository: ItemRepository) : ViewModel() {
    private val _state = MutableStateFlow<UiState>(UiState.Loading)
    val state: StateFlow<UiState> = _state.asStateFlow()

    fun onEvent(event: UiEvent) {
        when (event) {
            is UiEvent.Refresh -> loadItems()
            is UiEvent.ItemClicked -> navigateToDetail(event.id)
        }
    }
}

@Composable
fun ItemsScreen(viewModel: ItemsViewModel = hiltViewModel()) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    when (val s = state) {
        is UiState.Loading -> CircularProgressIndicator()
        is UiState.Success -> ItemsList(s.items) { id -> viewModel.onEvent(UiEvent.ItemClicked(id)) }
        is UiState.Error -> ErrorMessage(s.message) { viewModel.onEvent(UiEvent.Refresh) }
    }
}
```

**Rules:**
- `sealed class` / `sealed interface` for state, events, and navigation
- `data class` for states with data, `data object` for singletons
- ViewModels never hold references to `Context`, `View`, or `Activity`
- Use **Hilt** for dependency injection

## State Management Hierarchy (Compose)

1. `remember {}` — ephemeral, single-composable (animations, toggles)
2. `rememberSaveable {}` / `SavedStateHandle` — survives process death
3. `ViewModel` — survives config changes (rotation)
4. Scoped ViewModel (nav graph / activity) — shared multi-screen state
5. Hoist to parent composable — sibling composables needing shared state

## Concurrency

- Structured concurrency — never `GlobalScope`
- `viewModelScope` for Android, injected `CoroutineScope` elsewhere
- `Dispatchers.IO` for blocking I/O, `Dispatchers.Default` for CPU-heavy
- Expose reactive data as `Flow` / `StateFlow`

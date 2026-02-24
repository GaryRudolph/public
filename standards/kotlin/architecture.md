# Architecture — Kotlin

Follows general principles in [architecture.md](../architecture.md).

## Design Patterns

### MVI Pattern (Jetpack Compose)

MVI (Model-View-Intent) is the preferred pattern for Jetpack Compose. Its unidirectional data flow aligns with Compose's declarative recomposition model:

```kotlin
// State — single sealed interface for all screen states
sealed interface UiState {
    data object Loading : UiState
    data class Success(val items: List<Item>) : UiState
    data class Error(val message: String) : UiState
}

// Intent — user actions sent to the ViewModel
sealed interface UiEvent {
    data object Refresh : UiEvent
    data class ItemClicked(val id: String) : UiEvent
    data class SearchChanged(val query: String) : UiEvent
}

// ViewModel — reduces events into state
class ItemsViewModel(
    private val repository: ItemRepository,
) : ViewModel() {

    private val _state = MutableStateFlow<UiState>(UiState.Loading)
    val state: StateFlow<UiState> = _state.asStateFlow()

    fun onEvent(event: UiEvent) {
        when (event) {
            is UiEvent.Refresh -> loadItems()
            is UiEvent.ItemClicked -> navigateToDetail(event.id)
            is UiEvent.SearchChanged -> search(event.query)
        }
    }

    private fun loadItems() {
        viewModelScope.launch {
            _state.value = UiState.Loading
            try {
                val items = repository.getItems()
                _state.value = UiState.Success(items)
            } catch (e: Exception) {
                _state.value = UiState.Error(e.message ?: "Unknown error")
            }
        }
    }
}

// Composable — observes state, sends events
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
- ViewModel exposes a single `StateFlow<UiState>` — UI sends `Event` objects, ViewModel reduces them into new state
- Use `sealed class` / `sealed interface` for state, events, and navigation
- Use `data class` for states carrying data, `data object` for singleton states
- ViewModels should never hold references to `Context`, `View`, or `Activity`
- Use **Hilt** for dependency injection

## State Management Hierarchy (Compose)

1. `remember {}` — ephemeral, single-composable state (animations, toggles)
2. `rememberSaveable {}` / `SavedStateHandle` — survives process death
3. `ViewModel` — survives configuration changes (rotation)
4. Scoped ViewModel (nav graph / activity) — shared multi-screen state
5. Hoist to parent composable — sibling composables needing shared state

## Concurrency Architecture

- Use structured concurrency — never use `GlobalScope`
- Launch coroutines in `viewModelScope` (Android) or an injected `CoroutineScope`
- Expose reactive data as `Flow` / `StateFlow` from repositories and ViewModels
- Use `Dispatchers.IO` for blocking I/O, `Dispatchers.Default` for CPU-heavy work
- Use `Dispatchers.Main` for UI updates (automatic in `viewModelScope`)

```kotlin
class UserRepository(private val api: UserApi) {
    fun getUsers(): Flow<List<User>> = flow {
        val users = api.fetchUsers()
        emit(users)
    }.flowOn(Dispatchers.IO)
}
```

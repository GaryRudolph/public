# State & Observation — Swift

Follows [architecture.md](./architecture.md).

How one component learns that another component's state changed (settings toggles, app state, store-to-store reactions). This is the single source of truth so the decision is not re-debated per feature.

## TL;DR

- In-process app state lives in `@MainActor @Observable` stores.
- SwiftUI observes automatically; non-SwiftUI / imperative consumers observe with `Observations { ... }` (SE-0475).
- `NotificationCenter` is NOT used for internal app state. It is allowed only as a transport across a background-actor / framework boundary that fans out to multiple anonymous subscribers, after which it feeds an `@Observable` view model.
- New code does not use `ObservableObject` / `@Published` / Combine for state, and does not build a "private `NotificationCenter`" facade — `Observations` supersedes that workaround.

## Why

- The **Observation framework** (`@Observable`) is the standard for app/UI state; it replaced `ObservableObject`.
- **`Observations`** is an `AsyncSequence` for observing `@Observable` properties **outside SwiftUI**. It has did-set semantics, coalesces redundant updates, and manages its own lifecycle (no manual re-arming).
- **`NotificationCenter` is discouraged for internal logic**: string keys + untyped payloads create hidden dependencies and runtime errors. Reserve it for system frameworks that require it.
- For decoupled broadcast between concurrency-native components, the modern alternative to Combine is **`AsyncStream`**.

## Availability

- `@Observable` stores: iOS 17 / macOS 14+.
- `Observations` async sequence (SE-0475): Swift 6.2 / the 2025 SDKs (iOS 26 / macOS 26).
- Older deployment targets: fall back to `withObservationTracking`, manually re-arming after every fire.

## The pattern

### 1. State store is `@MainActor @Observable`

Persistence stays in a separate plain `Sendable` layer (e.g. a `StoreManager` over `UserDefaults`). The `@Observable` store is the UI-facing facade and writes through to persistence. Use change-only setters so a no-op assignment neither persists nor emits an observation:

```swift
@MainActor
@Observable
final class AppSettings {
    private let store: StoreManager

    private var _imageRecognition: Bool
    var isImageRecognitionEnabled: Bool {
        get { _imageRecognition }
        set {
            guard newValue != _imageRecognition else { return } // change-only
            _imageRecognition = newValue                        // emits observation
            store.isImageRecognitionEnabled = newValue          // persist
        }
    }

    init(store: StoreManager) {
        self.store = store
        self._imageRecognition = store.isImageRecognitionEnabled
    }
}
```

A bare `@Observable var` emits on every assignment (even equal values). The private-backing + computed-setter guard is what gives "notify only when it actually changes."

### 2. SwiftUI consumers — observe automatically

```swift
struct OptionsView: View {
    @Bindable var settings: AppSettings
    var body: some View {
        Toggle("Image Recognition", isOn: $settings.isImageRecognitionEnabled)
    }
}
```

No subscriptions, no tokens. Only the properties read in `body` trigger re-render.

### 3. Imperative / non-SwiftUI consumers — `Observations { }`

For a view model (or AppKit menu bar) that must run side effects when state changes:

```swift
observationTask = Task { [weak self, settings] in
    for await (imageOn, embeddingsOn) in Observations({
        (settings.isImageRecognitionEnabled, settings.isEmbeddingsEnabled)
    }) {
        guard let self else { return }   // unwrap INSIDE the loop, not before
        self.apply(imageRecognition: imageOn, embeddings: embeddingsOn)
    }
}
// deinit { observationTask?.cancel() }
```

- The first emission delivers the current values (good for initial sync).
- You observe exactly the properties you read in the closure — that is how you know "which field" matters.
- Lifecycle = the `Task`. Cancel it on teardown.
- Retain cycles: unwrap `self` inside the loop; capturing/unwrapping `self` before the `for` keeps it alive for the lifetime of the sequence.

### How the four common requirements map

- Multiple observers: inherent — any number of views + `Observations` tasks.
- Unregister on unload: SwiftUI is automatic; `Observations` is tied to a cancellable `Task`.
- Identify which field changed: observe the specific properties you read in the closure (or a tuple of them).
- Only on actual change: add an equality `guard` in the setter (see §1).

## The one sanctioned boundary exception

When the producer is a **background actor in a separate package** broadcasting to several **anonymous** subscribers (e.g. an indexing engine posting progress to the app), `NotificationCenter` (or an `AsyncStream` broadcast) is the correct transport, because:

- A `@MainActor` consumer can remove a `NotificationCenter` observer **synchronously in `deinit`**; an actor-held closure registry would require an `async` deregistration, which `deinit` cannot `await`.
- The producer holds **no references** to subscribers (no inverted dependency across the package boundary).
- Subscription is synchronous and does not have to `await` into a busy actor.

Shape: `actor engine --(NotificationCenter / AsyncStream)--> @Observable @MainActor view model --(Observation)--> UI`. Keep typed accessors over the notification payload; do not let raw `NotificationCenter` calls leak into multiple call sites. `Notification.Name` constants are reserved for this boundary only.

## Anti-patterns

- `NotificationCenter` for app-side state changes (settings, navigation, selection).
- A "private `NotificationCenter` instance" facade to simulate observers — use `Observations` instead.
- `ObservableObject` / `@Published` / Combine pipelines for new state. Migrate existing `ObservableObject` view models to `@Observable`. (Combine is fine only for genuine multi-stream operator chains.)
- Caching another store's value at `init` and never refreshing it (the staleness bug this standard exists to prevent).
- `@Observable var` without an equality guard when "change-only" semantics are required.

## Checklist for a new cross-component reaction

1. Is the producer in-process and main-actor? -> put the state in a `@MainActor @Observable` store.
2. SwiftUI consumer? -> read it directly / `@Bindable`.
3. Imperative consumer? -> `Observations { }` in a cancellable `Task`.
4. Need change-only? -> equality `guard` in the setter.
5. Producer is a background actor / separate framework with multiple subscribers? -> `NotificationCenter`/`AsyncStream` transport into an `@Observable` view model, then Observation downstream.

## References

- [Observation framework guide (2026)](https://swiftcrafted.dev/article/swiftui-observable-macro-complete-guide-observation-framework)
- [`Observations` outside SwiftUI (Donny Wals)](https://www.donnywals.com/using-observations-to-observe-observable-model-properties/)
- [SE-0475 `Observations`](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0475-observed.md)
- [`withObservationTracking` outside SwiftUI (Nil Coalescing)](https://nilcoalescing.com/blog/ObservationFrameworkOutsideOfSwiftUI)
- [Communication between observable stores (AzamSharp)](https://azamsharp.com/2025/08/17/effective-communication-between-observable-stores.html)

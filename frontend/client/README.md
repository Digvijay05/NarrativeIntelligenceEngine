# Client Architecture

This directory contains the Scaffold for the React/Next.js frontend application.
It strictly adheres to the **4-Layer Architecture** defined in the contract layer.

## Directory Structure

```
src/
├── layers/
│   ├── state/          # Read-Only Access to Backend Narrative State
│   │   ├── adapter.ts  # Typesafe fetcher for DTOs
│   │   └── hooks.ts    # React hooks for lifecycle-aware data access
│   │
│   ├── visualization/  # Deterministic Rendering Logic
│   │   ├── timeline/   # Transformations: NarrativeThreadDTO -> TimelineView
│   │   └── graph/      # Transformations: EntityRelations -> GraphView
│   │
│   ├── interaction/    # Temporal Control & Action Dispatch
│   │   ├── store.ts    # Zustand store for TemporalControlState
│   │   └── actions.ts  # Dispatchers for InteractionRequest
│   │
│   └── presentation/   # Pure UI Components
│       ├── components/ # Stateless components (ThreadCard, TimelineCanvas)
│       └── layouts/    # Composition of components
```

## Strict Rules

1.  **Presentation** components NEVER import from **State**.
    *   They only accept ViewModels props.
2.  **Visualization** logic is Pure Functions.
    *   Input: DTO + Config -> Output: Renderable Structure (TimelineView).
3.  **Interaction** never mutates state directly.
    *   It dispatches `InteractionRequests`.
4.  **State** is Read-Only.
    *   No local "optimistic updates" that hide uncertainty.

## Integration Flow

1.  User clicks "Play" -> **Interaction Layer** dispatches `PLAY_FORWARD`.
2.  **Interaction Layer** updates `TemporalControlState` (current_time).
3.  **Visualization Layer** recalculates `TimelineView` based on new `current_time`.
4.  **Presentation Layer** re-renders canvas.

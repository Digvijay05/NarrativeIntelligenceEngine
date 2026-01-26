# Narrative Intelligence Engine - Project Summary

## Overview
A strict, event-sourced narrative intelligence system designed to ingest, track, and visualize conflicting narratives without inferring truth or resolving ambiguity. The system acts as a "Forensic Instrument" rather than a news aggregator.

## System Architecture

### 1. Ingestion Layer (Python)
*   **Modular Fetching**: Supports RSS/Atom feeds with explicit tiering.
*   **Raw Storage**: Saves every byte of raw payload before parsing.
*   **Extraction**: Normalizes content into `EvidenceFragment` entities.

### 2. Core Narrative Engine (Python)
*   **Event Sourcing**: All state changes are immutable events (append-only log).
*   **6-Layer Model**:
    1.  **Ingestion**: Raw data capture.
    2.  **Normalization**: Canonical entities.
    3.  **Core Engine**: State machine processing.
    4.  **Storage**: SQLite/File-based temporal storage.
    5.  **Adapter**: Model overlay integration.
    6.  **Frontend**: Immutable DTO contracts.
*   **Key Guarantees**:
    *   No adjudication of truth.
    *   First-class support for absence and silence.
    *   Parallel, contradictory timelines coexist.

### 3. Frontend Client (React + Vite + Tailwind)
*   **Forensic Instrument UI**: Deterministic oscilloscope for narrative states.
*   **4-Layer Architecture**:
    *   **State**: Read-only access to backend DTOs.
    *   **Visualization**: Pure, deterministic D3.js layouts.
    *   **Interaction**: Temporal control (Zustand) without derived logic.
    *   **Presentation**: Stateless Tailwind CSS components.
*   **Design Philosophy**: Low-chroma "Forensic Palette", no sentiment hints, explicit divergence.

## Progress & Milestones

### ✅ Backend Implementation
*   Complete Event Sourcing engine.
*   Narrative Thread evolution logic (clustering, branching).
*   Model Adapter for "Divergence Scoring" (mocked/interfaced).

### ✅ Verification & Testing
*   **Chaos Test Suite**: 43/43 tests passed. Proven resilience against:
    *   Temporal contradictions (future timestamps).
    *   Out-of-order event delivery.
    *   Adversarial flooding.
*   **End-to-End Demo**: Verified full pipeline from RSS fetch to Frontend DTO generation.

### ✅ Frontend Implementation
*   **Scaffold**: Next-gen stack (React 18, Vite, Tailwind).
*   **Core Layers**: Implemented State, Visualization (TimelineLayout), and Interaction stores.
*   **Components**: Built `TimelineCanvas` (SVG renderer) and `Scrubber` controls.
*   **Integration**: Wired end-to-end with adversarial fixtures (Mock Adapter).

## Current Status
The project is in a **functional prototype state**.
*   **Backend**: Stable and verified.
*   **Frontend**: Implemented and runnable (`npm run dev`). Visualizes mock adversarial data effectively.

## Next Steps
1.  **API Connection**: Replace Frontend `StateAdapter` fixtures with real HTTP calls to Backend.
2.  **Deployment**: Containerize (Docker) the Python API and React Client.

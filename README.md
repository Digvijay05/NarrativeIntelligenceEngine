# Narrative Intelligence Engine

**A Forensic Instrument for Narrative Analysis**

> *Reconstruct coherent narratives from fragmented public information without inferring truth or resolving ambiguity.*

## Overview

The Narrative Intelligence Engine is an event-sourced system designed to ingest, normalize, and visualize conflicting narratives as they evolve over time. Unlike news aggregators or sentiment dashboards, it treats narrative evolution as a **temporal signals processing problem**.

**Key Principles:**
*   **No Interpretation**: The system does not rank "importance" or predict "truth".
*   **Forensic Rigor**: Every visualized state is traceable to a raw, immutable evidence fragment.
*   **First-Class Absence**: Silence, gaps, and disappearance are treated as signals, not missing data.
*   **Contradiction**: Parallel, mutually exclusive narratives are visualized side-by-side.

---

## 🏗 System Architecture

The system operates on a strict 6-layer Backend and 4-layer Frontend architecture.

### Backend (Python)
An event-sourced engine that processes raw feeds into narrative threads.

1.  **Ingestion Layer**: Fetches data (RSS/Atom) and stores *raw bytes* before parsing.
2.  **Normalization Layer**: Extracts entities into standard `EvidenceFragment` format.
3.  **Core Engine**: A deterministic state machine that evolves `NarrativeThread` entities.
4.  **Storage Layer**: Temporal storage preserving all history.
5.  **Adapter Layer**: Interfaces with ML models for "Divergence Scoring" (Overlay pattern).
6.  **Contract Layer**: Defines immutable DTOs for the frontend.

### Frontend (React + Vite + Tailwind)
A "Narrative Oscilloscope" web interface.

1.  **State Layer**: Read-only access to backend DTOs.
2.  **Visualization Layer**: Pure, deterministic D3.js layouts (Same Input → Same Pixels).
3.  **Interaction Layer**: Temporal control (Zustand) for scrubbing and replay.
4.  **Presentation Layer**: Stateless, "Forensic Palette" UI components.

---

## 🚀 Getting Started

### Prerequisites
*   **Python 3.11+**
*   **Node.js 18+** & `npm`

### 1. Backend Setup
The backend runs the ingestion and analysis pipeline.

```bash
# Data ingestion & Processing Demo
python end_to_end_demo.py
```
*This script runs a full cycle: Mock RSS fetch → Ingestion → Thread Creation → Analysis → DTO Generation.*

### 2. Frontend Setup
The frontend provides the interactive visualization.

```bash
cd et_hackathon_project/frontend/client
npm install
npm run dev
```
Access the UI at `http://localhost:5173`.

---

## 🧪 Verification & Status

The system is currently in **Functional Prototype** status.

*   **Chaos Tests**: `43/43 PASSED`. The engine is resilient against out-of-order events, future timestamps, and adversarial flooding.
*   **Integration**: End-to-end pipeline verified from RSS to DTO.
*   **UI Status**: Visualization layer implements strict deterministic timeline rendering.

### Capabilities (Current)
*   ✅ Ingest RSS feeds (tiered source quality).
*   ✅ Detect and track disjoint narrative threads.
*   ✅ Identify contradictions (via Mock Adapter).
*   ✅ Visualize silence and dormancy.

---

## 📂 Project Structure

```
├── backend/            # Core Python Engine
├── frontend/
│   ├── client/         # React Application
<!-- │   ├── state/          # Python DTO Contracts -->
│   ├── visualization/  # Python Visualization Contracts
│   └── interaction/    # Interaction Contracts
├── ingestion/          # Data Fetching & Parsing
├── models/             # Domain Entities
└── tests/              # Verification & Chaos Suites
```

---

## Developer Notes

*   **Immutability**: Ensure all DTOs remain frozen.
*   **Time Travel**: The frontend supports arbitrary historical replay.
*   **Zero Inference**: Do not add summary features or "AI insight" bubbles. The user is the analyst; the machine is the lens.

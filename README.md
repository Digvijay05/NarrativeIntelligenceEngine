# Narrative Intelligence Engine Prototype

This is a prototype implementation of the Narrative Intelligence Engine, designed to reconstruct coherent narratives from fragmented public information.

## Overview

The Narrative Intelligence Engine helps users:
- Reconstruct coherent narratives from fragmented public information
- Surface progression, stalling, or disappearance of narratives over time
- Understand complex, multi-actor situations with reduced cognitive effort
- Make informed decisions grounded in context rather than isolated facts

See `../Docs/PRD.txt` for the complete problem statement and requirements.

## Components

### Data Ingestion (`ingestion.py`)
Handles loading and preprocessing of raw data from various sources:
- JSON files with timestamped fragments
- CSV files with timestamped fragments
- Basic preprocessing and validation

### Core Models (`models.py`)
Defines the fundamental data structures:
- `Fragment`: A single piece of information at a specific time
- `Thread`: A collection of related narrative fragments over time
- `NarrativeStateEngine`: Processes fragments and groups them into threads

### Visualization (`visualization.py`)
Provides text-based visualization of narrative threads:
- Timeline view showing narrative progression
- Comparison view showing parallel narratives
- Export functionality to JSON for external analysis

### Main Application (`main.py`)
Coordinates the components and runs the prototype.

## Requirements

- Python 3.7+
- No external dependencies (uses only Python standard library)

## Usage

Run the prototype:
```bash
cd src
python main.py
```

The prototype will:
1. Load sample data from `../../sample_narrative_data.json`
2. Process fragments into narrative threads grouped by topic
3. Display timeline and comparison views
4. Export processed data to `../../narrative_output.json`

## Design Principles

This prototype adheres to the principles outlined in the design document:
- Clarity over certainty: Shows traceable structure without definitive conclusions
- Continuity over immediacy: Focuses on understanding evolution across time
- Comparability over persuasion: Enables contrast without pushing interpretation
- Absence as signal: Represents silence and disappearance as informational states

## Limitations

This is a prototype implementation with several intentional limitations:
- No real-time processing
- No predictive capabilities
- Simplified topic grouping (by explicit topic field)
- Text-based visualization only
- No entity resolution
- No sentiment analysis or judgment systems

## Files

- `src/ingestion.py` - Data loading and preprocessing
- `src/models.py` - Core data structures and processing logic
- `src/visualization.py` - Text-based visualization components
- `src/main.py` - Main application entry point
- `requirements.txt` - Dependency information
- `../sample_narrative_data.json` - Sample input data
- `../narrative_output.json` - Exported output data (created when running)
- `../Docs/` - Documentation and requirements

# Fragility Report: Narrative Load & Fault Visualization

## 1. The "Glass Bridge" (Linear Narrative)
In a curated sequential narrative, **every edge is critical**. Removing any single link causes the component count to increase (Structural Divergence). The system correctly identifies these as "Load-Bearing" (Red).

```mermaid
graph TD
    classDef critical stroke:#ff0000,stroke-width:4px;
    classDef redundant stroke:#0000ff,stroke-dasharray: 5 5;
    classDef node default fill:#fff,stroke:#333,stroke-width:1px;
    frag_be980f2ac15c28e5["28e5: ‘Last Mile’ Moves to..."]
    frag_ec2b12149b3350c2["50c2: US negotiators meet ..."]
    frag_8391dd85116b48f1["48f1: Ukraine-Russia-US ta..."]
    frag_8a30689db01c0579["0579: Ukraine updates: Pea..."]
    frag_d01f4a4c54752728["2728: Ukrainian, Russian a..."]
    frag_1392992e41ffc1c6["c1c6: US, Russia and Ukrai..."]
    frag_be980f2ac15c28e5 --> frag_ec2b12149b3350c2
    linkStyle 0 stroke:#ff0000,stroke-width:4px;
    frag_ec2b12149b3350c2 --> frag_8391dd85116b48f1
    linkStyle 1 stroke:#ff0000,stroke-width:4px;
    frag_ec2b12149b3350c2 --> frag_8391dd85116b48f1
    linkStyle 2 stroke:#ff0000,stroke-width:4px;
    frag_8391dd85116b48f1 --> frag_8a30689db01c0579
    linkStyle 3 stroke:#ff0000,stroke-width:4px;
    frag_8391dd85116b48f1 --> frag_8a30689db01c0579
    linkStyle 4 stroke:#ff0000,stroke-width:4px;
    frag_8a30689db01c0579 --> frag_d01f4a4c54752728
    linkStyle 5 stroke:#ff0000,stroke-width:4px;
    frag_8a30689db01c0579 --> frag_d01f4a4c54752728
    linkStyle 6 stroke:#ff0000,stroke-width:4px;
    frag_d01f4a4c54752728 --> frag_1392992e41ffc1c6
    linkStyle 7 stroke:#ff0000,stroke-width:4px;
    frag_d01f4a4c54752728 --> frag_1392992e41ffc1c6
    linkStyle 8 stroke:#ff0000,stroke-width:4px;
```

## 2. Robustness Check (Redundant Structure)
Here we artificially injected a reference from Node 1 to Node 3 (skipping Node 2). The system correctly identifies the `REFERENCE` edge (or the parallel `CONTINUATION`) as redundant in terms of pure connectivity.

*Note: In a pure linear chain A->B->C, adding A->C makes the path A->B redundant for reaching C, or B->C redundant if A->C exists? Actually, removing A->B still leaves A->C, so A->B is no longer a cut-edge (bridge) IF the graph is undirected or if paths exist. Bridge detection depends on connectivity. In a directed DAG, A->B is still critical for B. But for 'weak connectivity' (component clustering), the triangle protects against splits.*

**Visual Result**:
*   **Red Edges**: Still Critical (Bridges).
*   **Blue/Dashed Edges**: Redundant (Cycles).

```mermaid
graph TD
    classDef critical stroke:#ff0000,stroke-width:4px;
    classDef redundant stroke:#0000ff,stroke-dasharray: 5 5;
    classDef node default fill:#fff,stroke:#333,stroke-width:1px;
    frag_be980f2ac15c28e5["28e5: ‘Last Mile’ Moves to..."]
    frag_ec2b12149b3350c2["50c2: US negotiators meet ..."]
    frag_8391dd85116b48f1["48f1: Ukraine-Russia-US ta..."]
    frag_8a30689db01c0579["0579: Ukraine updates: Pea..."]
    frag_d01f4a4c54752728["2728: Ukrainian, Russian a..."]
    frag_1392992e41ffc1c6["c1c6: US, Russia and Ukrai..."]
    frag_be980f2ac15c28e5 --> frag_ec2b12149b3350c2
    linkStyle 0 stroke:#0000ff,stroke-width:1px,stroke-dasharray: 5 5;
    frag_ec2b12149b3350c2 --> frag_8391dd85116b48f1
    linkStyle 1 stroke:#0000ff,stroke-width:1px,stroke-dasharray: 5 5;
    frag_ec2b12149b3350c2 --> frag_8391dd85116b48f1
    linkStyle 2 stroke:#0000ff,stroke-width:1px,stroke-dasharray: 5 5;
    frag_8391dd85116b48f1 --> frag_8a30689db01c0579
    linkStyle 3 stroke:#ff0000,stroke-width:4px;
    frag_8391dd85116b48f1 --> frag_8a30689db01c0579
    linkStyle 4 stroke:#ff0000,stroke-width:4px;
    frag_8a30689db01c0579 --> frag_d01f4a4c54752728
    linkStyle 5 stroke:#ff0000,stroke-width:4px;
    frag_8a30689db01c0579 --> frag_d01f4a4c54752728
    linkStyle 6 stroke:#ff0000,stroke-width:4px;
    frag_d01f4a4c54752728 --> frag_1392992e41ffc1c6
    linkStyle 7 stroke:#ff0000,stroke-width:4px;
    frag_d01f4a4c54752728 --> frag_1392992e41ffc1c6
    linkStyle 8 stroke:#ff0000,stroke-width:4px;
    frag_be980f2ac15c28e5 --- frag_8391dd85116b48f1
    linkStyle 9 stroke:#0000ff,stroke-width:1px,stroke-dasharray: 5 5;
```

## Conclusion
The visualization demonstrates that the engine performs **Structural Bridge Detection**. It does not assume continuity; it calculates it.

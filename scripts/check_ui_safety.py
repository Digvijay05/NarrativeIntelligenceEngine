"""
UI Safety Linter
================

Enforces the "Anti-Constitution" for frontend development.
Ensures the UI does not act as a narrator by forbidding interpolation, smoothing, and prediction.

USAGE:
    python scripts/check_ui_safety.py [directory]
"""
import os
import sys
import re

FORBIDDEN_PATTERNS = [
    (r"interpolate", "Interpolation implies continuity where gaps may exist."),
    (r"smooth", "Smoothing hides outliers and structural conflicts."),
    (r"average", "Averaging hides raw data points."),
    (r"predict", "Prediction is forbidden. The system is forensic, not predictive."),
    (r"d3\.line", "Line charts imply continuity. Use scatter plots or step functions."),
    (r"curveBasis", "Curved lines are strictly forbidden."),
    (r"tomcat", "No unauthorized server names (Example)."),
]

def scan_file(filepath):
    """Scan a single file for forbidden patterns."""
    violations = []
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            content = f.read()
            lines = content.split('\n')
            for i, line in enumerate(lines):
                for pattern, reason in FORBIDDEN_PATTERNS:
                    if re.search(pattern, line, re.IGNORECASE):
                        violations.append({
                            "line": i + 1,
                            "pattern": pattern,
                            "reason": reason,
                            "content": line.strip()
                        })
        except Exception as e:
            print(f"Could not read {filepath}: {e}")
            
    return violations

def check_directory(start_dir):
    """Recursively scan directory."""
    print(f"[*] Scanning {start_dir} for UI Constitution violations...")
    
    total_violations = 0
    scanned_files = 0
    
    for root, dirs, files in os.walk(start_dir):
        if "node_modules" in dirs:
            dirs.remove("node_modules")
        if "__pycache__" in dirs:
            dirs.remove("__pycache__")
            
        for file in files:
            if file.endswith(('.js', '.jsx', '.ts', '.tsx', '.css', '.html')):
                scanned_files += 1
                path = os.path.join(root, file)
                violations = scan_file(path)
                
                if violations:
                    print(f"\n[FAIL] {path}")
                    for v in violations:
                        print(f"    L{v['line']}: {v['reason']}")
                        print(f"    Code: {v['content']}")
                    total_violations += len(violations)

    print("\n--------------------------------------------------")
    if total_violations == 0:
        print(f"[PASS] Scanned {scanned_files} files. No violations found.")
        sys.exit(0)
    else:
        print(f"[FAIL] Found {total_violations} violations in {scanned_files} files.")
        sys.exit(1)

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    check_directory(target)

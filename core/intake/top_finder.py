"""
Top-Level Module Identification & Verification Testbench Classifier.
Uses in-degree analysis and naming heuristics to pick the root design entity.
"""

import os
from typing import List, Tuple
from .source_scanner import SourceFile, is_testbench_content


def classify_testbench(source: SourceFile) -> bool:
    return source.is_testbench


def find_top_candidates(sources: List[SourceFile]) -> List[Tuple[str, SourceFile, int]]:
    """
    Identifies candidate top-level modules from synthesizable files.
    Returns a list of tuples: (module_name, SourceFile, confidence_score)
    sorted in descending order of confidence score.
    """
    candidates = []
    rtl_files = [s for s in sources if not s.is_testbench]
    if not rtl_files:
        return candidates

    # Build reference counts: which declared units are instantiated by others?
    referenced_units = set()
    for s in rtl_files:
        for req in s.required_units:
            referenced_units.add(req.lower())

    for s in rtl_files:
        for unit in s.declared_units:
            u_lower = unit.lower()
            score = 0

            # 1. Root Entity: declared but never instantiated by any other file
            # If instantiated, check if it was only as a component in a package
            is_pkg_file = any("package" in p.lower() or "_pkg" in p.lower() for p in [s.path])
            if u_lower not in referenced_units:
                score += 50
            else:
                score -= 10

            # 2. Highest compilation tier (compiled near or at the end)
            score += min(30, s.tier * 4)

            # 3. Naming Heuristics
            if u_lower.endswith("_top") or u_lower == "top":
                score += 120
            elif any(k in u_lower for k in ("_top", "top_", "soc", "core_complex", "chip")):
                score += 80
            elif "core" in u_lower or "cpu" in u_lower:
                score += 40

            # Filename alignment: unit name matches filename
            base_file = os.path.splitext(os.path.basename(s.path))[0].lower()
            if u_lower == base_file:
                score += 10

            # Penalize packages/types
            if any(k in u_lower for k in ("package", "_pkg", "types", "constants")):
                score -= 100

            candidates.append((unit, s, score))

    candidates.sort(key=lambda x: x[2], reverse=True)
    return candidates

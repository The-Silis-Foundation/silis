"""
Dependency Graph & Topological Sorter for SILIS Intake Engine.
Orders files logically according to Kahn's algorithm so that packages,
primitives, and components compile before top entities.
"""

from typing import List, Dict, Set
from .source_scanner import SourceFile


class DependencyGraph:
    def __init__(self, sources: List[SourceFile]):
        self.sources = sources
        self.unit_to_file: Dict[str, SourceFile] = {}
        for s in sources:
            for u in s.declared_units:
                self.unit_to_file[u.lower()] = s

    def get_dependencies_for_file(self, src: SourceFile) -> Set[SourceFile]:
        deps: Set[SourceFile] = set()
        for req in src.required_units:
            req_lower = req.lower()
            if req_lower in self.unit_to_file:
                target_file = self.unit_to_file[req_lower]
                if target_file.path != src.path:
                    deps.add(target_file)
        return deps


def topological_sort(sources: List[SourceFile]) -> List[SourceFile]:
    """
    Performs Kahn's algorithm on the source files based on declared vs required units.
    Files without dependencies (packages, types) appear first.
    Returns files in valid compilation order with .tier populated.
    """
    if not sources:
        return []

    # Filter out testbenches for synthesis sorting (keep separate)
    rtl_sources = [s for s in sources if not s.is_testbench]
    tb_sources = [s for s in sources if s.is_testbench]

    graph = DependencyGraph(rtl_sources)

    # Calculate in-degree (number of files that `src` depends on)
    in_degree: Dict[str, int] = {}
    dep_map: Dict[str, Set[SourceFile]] = {}
    rev_dep_map: Dict[str, Set[SourceFile]] = {s.path: set() for s in rtl_sources}

    for s in rtl_sources:
        deps = graph.get_dependencies_for_file(s)
        dep_map[s.path] = deps
        in_degree[s.path] = len(deps)
        for d in deps:
            rev_dep_map[d.path].add(s)

    # Queue of nodes with 0 dependencies
    queue: List[SourceFile] = [s for s in rtl_sources if in_degree[s.path] == 0]

    # Heuristic tie-breaker: packages always first
    def tie_break_key(sf: SourceFile):
        p_lower = sf.path.lower()
        if "package" in p_lower or "_pkg" in p_lower:
            return 0
        if "prim" in p_lower or "sys" in p_lower:
            return 1
        return 2

    queue.sort(key=tie_break_key)

    sorted_result: List[SourceFile] = []
    current_tier = 0

    while queue:
        # Collect all nodes at the current tier
        current_level = list(queue)
        queue = []

        for node in current_level:
            node.tier = current_tier
            sorted_result.append(node)

            for dependent in rev_dep_map[node.path]:
                in_degree[dependent.path] -= 1
                if in_degree[dependent.path] == 0:
                    queue.append(dependent)

        queue.sort(key=tie_break_key)
        current_tier += 1

    # Check for cycles
    if len(sorted_result) < len(rtl_sources):
        missing = [s for s in rtl_sources if s not in sorted_result]
        # Append remaining nodes at the end to prevent total crash
        for m in missing:
            m.tier = current_tier
            sorted_result.append(m)

    # Append testbenches at the very end
    for tb in tb_sources:
        tb.tier = current_tier + 1
        sorted_result.append(tb)

    return sorted_result

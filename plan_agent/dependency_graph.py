"""
Dependency Graph - Manages action dependencies and computes execution order.
"""

from __future__ import annotations

from typing import Any


class DependencyGraph:
    """
    Manages dependencies between actions and computes topological ordering.
    """
    
    def __init__(self):
        """Initialize an empty dependency graph."""
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: dict[str, list[str]] = {}  # action_id -> list of dependency action_ids
    
    def add_node(self, action_id: str, action_data: dict[str, Any]) -> None:
        """
        Add an action node to the graph.
        
        Args:
            action_id: Unique action identifier
            action_data: Action data dictionary
        """
        self.nodes[action_id] = action_data
        if action_id not in self.edges:
            self.edges[action_id] = []
    
    def add_dependency(self, action_id: str, depends_on: str) -> None:
        """
        Add a dependency between actions.
        
        Args:
            action_id: Action that depends on another
            depends_on: Action that must be executed first
        """
        if action_id not in self.edges:
            self.edges[action_id] = []
        self.edges[action_id].append(depends_on)
    
    def validate_no_cycles(self) -> tuple[bool, list[str]]:
        """
        Check for circular dependencies using DFS.
        
        Returns:
            Tuple of (is_valid, cycle_path if found)
        """
        visited = set()
        rec_stack = set()
        
        def has_cycle(node: str, path: list[str]) -> tuple[bool, list[str]]:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)
            
            for neighbor in self.edges.get(node, []):
                if neighbor not in visited:
                    has_cycle_result, cycle = has_cycle(neighbor, path.copy())
                    if has_cycle_result:
                        return True, cycle
                elif neighbor in rec_stack:
                    # Found a cycle
                    cycle_start = path.index(neighbor)
                    return True, path[cycle_start:] + [neighbor]
            
            rec_stack.remove(node)
            return False, []
        
        for node in self.nodes:
            if node not in visited:
                has_cycle_result, cycle = has_cycle(node, [])
                if has_cycle_result:
                    return False, cycle
        
        return True, []
    
    def topological_sort(self) -> list[str]:
        """
        Perform topological sort to determine execution order.
        
        Returns:
            List of action IDs in execution order
            
        Raises:
            ValueError: If graph contains cycles
        """
        is_valid, cycle = self.validate_no_cycles()
        if not is_valid:
            raise ValueError(f"Circular dependency detected: {' -> '.join(cycle)}")
        
        # Kahn's algorithm for topological sort
        # In our graph, edges[node] = list of dependencies (nodes that must come before)
        # So in_degree[node] = number of dependencies node has
        in_degree = {node: len(self.edges.get(node, [])) for node in self.nodes}
        
        # Find nodes with no dependencies (in_degree == 0)
        queue = [node for node in self.nodes if in_degree[node] == 0]
        result = []
        
        while queue:
            # Sort to ensure deterministic ordering
            queue.sort()
            node = queue.pop(0)
            result.append(node)
            
            # Find all nodes that depend on this node and reduce their in_degree
            for dependent in self.nodes:
                if node in self.edges.get(dependent, []):
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
        
        if len(result) != len(self.nodes):
            raise ValueError("Graph contains cycles or disconnected components")
        
        return result
    
    def get_dependencies(self, action_id: str) -> list[str]:
        """
        Get direct dependencies for an action.
        
        Args:
            action_id: Action identifier
            
        Returns:
            List of action IDs this action depends on
        """
        return self.edges.get(action_id, [])
    
    def to_dict(self) -> dict[str, Any]:
        """
        Export graph as dictionary for JSON serialization.
        
        Returns:
            Dictionary representation of the graph
        """
        return {
            "nodes": list(self.nodes.keys()),
            "edges": [
                {
                    "from": action_id,
                    "to": dep_id
                }
                for action_id, deps in self.edges.items()
                for dep_id in deps
            ]
        }

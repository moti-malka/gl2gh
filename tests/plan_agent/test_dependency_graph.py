"""
Tests for dependency graph.
"""

import pytest
from plan_agent.dependency_graph import DependencyGraph


def test_add_node():
    """Test adding nodes to the graph."""
    graph = DependencyGraph()
    graph.add_node("action_001", {"type": "create_repository"})
    
    assert "action_001" in graph.nodes
    assert graph.nodes["action_001"]["type"] == "create_repository"


def test_add_dependency():
    """Test adding dependencies between nodes."""
    graph = DependencyGraph()
    graph.add_node("action_001", {"type": "create_repository"})
    graph.add_node("action_002", {"type": "push_code"})
    
    graph.add_dependency("action_002", "action_001")
    
    assert "action_001" in graph.edges["action_002"]


def test_validate_no_cycles_valid():
    """Test cycle detection on a valid DAG."""
    graph = DependencyGraph()
    graph.add_node("action_001", {})
    graph.add_node("action_002", {})
    graph.add_node("action_003", {})
    
    graph.add_dependency("action_002", "action_001")
    graph.add_dependency("action_003", "action_002")
    
    is_valid, cycle = graph.validate_no_cycles()
    assert is_valid is True
    assert cycle == []


def test_validate_no_cycles_detects_cycle():
    """Test cycle detection identifies circular dependencies."""
    graph = DependencyGraph()
    graph.add_node("action_001", {})
    graph.add_node("action_002", {})
    graph.add_node("action_003", {})
    
    # Create a cycle: 1 -> 2 -> 3 -> 1
    graph.add_dependency("action_002", "action_001")
    graph.add_dependency("action_003", "action_002")
    graph.add_dependency("action_001", "action_003")
    
    is_valid, cycle = graph.validate_no_cycles()
    assert is_valid is False
    assert len(cycle) > 0


def test_validate_no_cycles_self_reference():
    """Test cycle detection identifies self-referencing nodes."""
    graph = DependencyGraph()
    graph.add_node("action_001", {})
    
    # Self-reference
    graph.add_dependency("action_001", "action_001")
    
    is_valid, cycle = graph.validate_no_cycles()
    assert is_valid is False


def test_topological_sort_simple():
    """Test topological sort on a simple graph."""
    graph = DependencyGraph()
    graph.add_node("action_001", {})
    graph.add_node("action_002", {})
    graph.add_node("action_003", {})
    
    # 001 -> 002 -> 003
    graph.add_dependency("action_002", "action_001")
    graph.add_dependency("action_003", "action_002")
    
    result = graph.topological_sort()
    
    # Check that dependencies come before dependents
    assert result.index("action_001") < result.index("action_002")
    assert result.index("action_002") < result.index("action_003")


def test_topological_sort_with_cycle_raises():
    """Test topological sort raises error for cyclic graph."""
    graph = DependencyGraph()
    graph.add_node("action_001", {})
    graph.add_node("action_002", {})
    
    # Create a cycle
    graph.add_dependency("action_001", "action_002")
    graph.add_dependency("action_002", "action_001")
    
    with pytest.raises(ValueError, match="Circular dependency detected"):
        graph.topological_sort()


def test_topological_sort_complex():
    """Test topological sort on a complex graph."""
    graph = DependencyGraph()
    
    # Create a diamond dependency:
    #     001
    #    /   \
    #  002   003
    #    \   /
    #     004
    
    graph.add_node("action_001", {})
    graph.add_node("action_002", {})
    graph.add_node("action_003", {})
    graph.add_node("action_004", {})
    
    graph.add_dependency("action_002", "action_001")
    graph.add_dependency("action_003", "action_001")
    graph.add_dependency("action_004", "action_002")
    graph.add_dependency("action_004", "action_003")
    
    result = graph.topological_sort()
    
    # Check that 001 comes first
    assert result.index("action_001") == 0
    
    # Check that 002 and 003 come before 004
    assert result.index("action_002") < result.index("action_004")
    assert result.index("action_003") < result.index("action_004")


def test_get_dependencies():
    """Test getting dependencies for a node."""
    graph = DependencyGraph()
    graph.add_node("action_001", {})
    graph.add_node("action_002", {})
    graph.add_node("action_003", {})
    
    graph.add_dependency("action_003", "action_001")
    graph.add_dependency("action_003", "action_002")
    
    deps = graph.get_dependencies("action_003")
    assert set(deps) == {"action_001", "action_002"}


def test_to_dict():
    """Test exporting graph to dictionary."""
    graph = DependencyGraph()
    graph.add_node("action_001", {})
    graph.add_node("action_002", {})
    graph.add_dependency("action_002", "action_001")
    
    result = graph.to_dict()
    
    assert "nodes" in result
    assert "edges" in result
    assert set(result["nodes"]) == {"action_001", "action_002"}
    assert len(result["edges"]) == 1
    assert result["edges"][0]["from"] == "action_002"
    assert result["edges"][0]["to"] == "action_001"

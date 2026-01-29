#!/usr/bin/env python3
"""
Simple validation script for Discovery Agent implementation

Checks code structure, imports, and basic functionality without
requiring full environment setup.
"""

import ast
import sys
from pathlib import Path


def check_file_syntax(filepath):
    """Check Python file syntax"""
    try:
        with open(filepath, 'r') as f:
            code = f.read()
        ast.parse(code)
        return True, "OK"
    except SyntaxError as e:
        return False, str(e)


def check_class_methods(filepath, class_name, required_methods):
    """Check if a class has required methods"""
    with open(filepath, 'r') as f:
        code = f.read()
    
    tree = ast.parse(code)
    
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == class_name:
            methods = {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
            missing = set(required_methods) - methods
            
            if missing:
                return False, f"Missing methods: {', '.join(missing)}"
            return True, f"All {len(required_methods)} required methods present"
    
    return False, f"Class {class_name} not found"


def count_component_detections(filepath):
    """Count how many component types are detected"""
    with open(filepath, 'r') as f:
        code = f.read()
    
    # Component keywords to search for
    components = [
        "repository", "ci_cd", "issues", "merge_requests", "wiki",
        "releases", "packages", "webhooks", "schedules", "lfs",
        "environments", "protected_resources", "deploy_keys", "variables"
    ]
    
    detected = []
    for comp in components:
        # Check if component is mentioned in component detection context
        if f'components["{comp}"]' in code or f"components['{comp}']" in code:
            detected.append(comp)
    
    return len(detected), detected


def main():
    """Run validation checks"""
    
    print("=" * 60)
    print("Discovery Agent Implementation Validation")
    print("=" * 60)
    
    backend_dir = Path(__file__).parent / "backend"
    
    # Files to check
    files_to_check = {
        "GitLab Client": backend_dir / "app/clients/gitlab_client.py",
        "Discovery Agent": backend_dir / "app/agents/discovery_agent.py",
        "Celery Tasks": backend_dir / "app/workers/tasks.py",
        "Unit Tests": backend_dir / "tests/test_discovery_agent.py",
    }
    
    all_ok = True
    
    print("\n1. Syntax Validation:")
    print("-" * 60)
    for name, filepath in files_to_check.items():
        if not filepath.exists():
            print(f"  ✗ {name}: File not found")
            all_ok = False
            continue
        
        ok, msg = check_file_syntax(filepath)
        status = "✓" if ok else "✗"
        print(f"  {status} {name}: {msg}")
        if not ok:
            all_ok = False
    
    # Check GitLab Client methods
    print("\n2. GitLab Client Methods:")
    print("-" * 60)
    gitlab_client_path = files_to_check["GitLab Client"]
    if gitlab_client_path.exists():
        required_methods = [
            "get_project", "list_projects", "list_branches", "list_tags",
            "list_issues", "list_merge_requests", "has_wiki", "list_releases",
            "has_ci_config", "list_pipelines", "list_environments",
            "list_variables", "list_hooks", "list_protected_branches",
            "list_deploy_keys", "has_lfs", "has_packages"
        ]
        
        ok, msg = check_class_methods(gitlab_client_path, "GitLabClient", required_methods)
        status = "✓" if ok else "✗"
        print(f"  {status} GitLabClient: {msg}")
        if not ok:
            all_ok = False
    
    # Check Discovery Agent methods
    print("\n3. Discovery Agent Methods:")
    print("-" * 60)
    discovery_agent_path = files_to_check["Discovery Agent"]
    if discovery_agent_path.exists():
        required_methods = [
            "execute", "validate_inputs", "assess_readiness",
            "generate_artifacts", "_detect_project_components",
            "_generate_inventory", "_generate_coverage", "_generate_readiness"
        ]
        
        ok, msg = check_class_methods(discovery_agent_path, "DiscoveryAgent", required_methods)
        status = "✓" if ok else "✗"
        print(f"  {status} DiscoveryAgent: {msg}")
        if not ok:
            all_ok = False
    
    # Check component detection
    print("\n4. Component Detection Coverage:")
    print("-" * 60)
    if discovery_agent_path.exists():
        count, detected = count_component_detections(discovery_agent_path)
        print(f"  Components detected: {count}/14")
        if count >= 14:
            print(f"  ✓ All 14 component types detected")
        else:
            print(f"  ✗ Missing some components")
            all_ok = False
        
        # List detected components
        for comp in detected:
            print(f"    • {comp}")
    
    # Check test coverage
    print("\n5. Unit Test Coverage:")
    print("-" * 60)
    test_path = files_to_check["Unit Tests"]
    if test_path.exists():
        with open(test_path, 'r') as f:
            test_code = f.read()
        
        # Count test methods
        tree = ast.parse(test_code)
        test_methods = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                test_methods.append(node.name)
        
        print(f"  ✓ Test methods: {len(test_methods)}")
        
        # List some tests
        for test_name in test_methods[:5]:
            print(f"    • {test_name}")
        if len(test_methods) > 5:
            print(f"    ... and {len(test_methods) - 5} more")
    
    # Check Celery task integration
    print("\n6. Celery Task Integration:")
    print("-" * 60)
    tasks_path = files_to_check["Celery Tasks"]
    if tasks_path.exists():
        with open(tasks_path, 'r') as f:
            tasks_code = f.read()
        
        checks = {
            "ArtifactService import": "from app.services import ArtifactService",
            "EventService import": "EventService",
            "Store artifacts": "store_artifact",
            "Create events": "create_event",
            "Store run_projects": "run_projects",
            "Update run status": "update_run_status"
        }
        
        for check_name, check_str in checks.items():
            found = check_str in tasks_code
            status = "✓" if found else "✗"
            print(f"  {status} {check_name}")
            if not found:
                all_ok = False
    
    # Summary
    print("\n" + "=" * 60)
    if all_ok:
        print("✓ All validation checks PASSED")
        print("=" * 60)
        return 0
    else:
        print("✗ Some validation checks FAILED")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""
Output Generator - Creates plan output files (JSON, Markdown, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schema import Plan, PhaseType


def generate_plan_markdown(plan: Plan) -> str:
    """
    Generate a human-readable markdown summary of the plan.
    
    Args:
        plan: Migration plan
        
    Returns:
        Markdown formatted string
    """
    md_lines = []
    
    # Header
    md_lines.append(f"# Migration Plan: {plan['project_id']}")
    md_lines.append("")
    md_lines.append(f"**Run ID:** `{plan['run_id']}`  ")
    md_lines.append(f"**Generated:** {plan['generated_at']}  ")
    md_lines.append(f"**Version:** {plan['version']}")
    md_lines.append("")
    
    # Statistics
    stats = plan["statistics"]
    md_lines.append("## Statistics")
    md_lines.append("")
    md_lines.append(f"- **Total Actions:** {stats['total_actions']}")
    md_lines.append(f"- **Actions Requiring User Input:** {stats['actions_requiring_user_input']}")
    md_lines.append(f"- **Total Dependencies:** {stats['total_dependencies']}")
    md_lines.append("")
    
    # Actions by Type
    md_lines.append("### Actions by Type")
    md_lines.append("")
    for action_type, count in sorted(stats["actions_by_type"].items()):
        md_lines.append(f"- `{action_type}`: {count}")
    md_lines.append("")
    
    # Actions by Phase
    md_lines.append("### Actions by Phase")
    md_lines.append("")
    for phase, count in sorted(stats["actions_by_phase"].items()):
        md_lines.append(f"- **{phase}**: {count} actions")
    md_lines.append("")
    
    # Phases and Actions
    md_lines.append("## Execution Plan by Phase")
    md_lines.append("")
    
    for phase_type in PhaseType:
        phase_name = phase_type.value
        action_ids = plan["phases"].get(phase_name, [])
        
        if not action_ids:
            continue
        
        md_lines.append(f"### Phase: {phase_name.replace('_', ' ').title()}")
        md_lines.append("")
        
        # Find actions for this phase
        phase_actions = [a for a in plan["actions"] if a["id"] in action_ids]
        
        for action in phase_actions:
            icon = "🔴" if action.get("requires_user_input", False) else "🟢"
            md_lines.append(f"{icon} **{action['id']}**: {action['description']}")
            
            if action.get("dependencies"):
                md_lines.append(f"   - Dependencies: {', '.join(action['dependencies'])}")
            
            if action.get("requires_user_input", False):
                md_lines.append(f"   - ⚠️ **Requires user input**")
                for field in action.get("user_input_fields", []):
                    md_lines.append(f"      - `{field['name']}`: {field['description']}")
            
            md_lines.append("")
        
        md_lines.append("")
    
    # User Input Summary
    user_input_actions = [a for a in plan["actions"] if a.get("requires_user_input", False)]
    if user_input_actions:
        md_lines.append("## Actions Requiring User Input")
        md_lines.append("")
        md_lines.append("The following actions require manual user input before execution:")
        md_lines.append("")
        
        for action in user_input_actions:
            md_lines.append(f"### {action['id']}")
            md_lines.append(f"**Description:** {action['description']}  ")
            md_lines.append(f"**Type:** `{action['action_type']}`")
            md_lines.append("")
            md_lines.append("**Required Inputs:**")
            for field in action.get("user_input_fields", []):
                md_lines.append(f"- `{field['name']}`: {field['description']}")
            md_lines.append("")
    
    return "\n".join(md_lines)


def save_plan_outputs(plan: Plan, output_dir: Path, dependency_graph: Any) -> None:
    """
    Save all plan output files to the specified directory.
    
    Args:
        plan: Migration plan
        output_dir: Directory to save outputs
        dependency_graph: Dependency graph instance
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save plan.json
    plan_json_path = output_dir / "plan.json"
    with open(plan_json_path, "w") as f:
        json.dump(plan, f, indent=2)
    
    # Save plan.md
    plan_md_path = output_dir / "plan.md"
    with open(plan_md_path, "w") as f:
        f.write(generate_plan_markdown(plan))
    
    # Save dependency_graph.json
    dep_graph_path = output_dir / "dependency_graph.json"
    with open(dep_graph_path, "w") as f:
        json.dump(dependency_graph.to_dict(), f, indent=2)
    
    # Save user_inputs_required.json
    user_inputs = [
        {
            "action_id": action["id"],
            "action_type": action["action_type"],
            "description": action["description"],
            "user_input_fields": action.get("user_input_fields", []),
        }
        for action in plan["actions"]
        if action.get("requires_user_input", False)
    ]
    
    user_inputs_path = output_dir / "user_inputs_required.json"
    with open(user_inputs_path, "w") as f:
        json.dump({"user_inputs_required": user_inputs}, f, indent=2)
    
    # Save plan_stats.json
    plan_stats_path = output_dir / "plan_stats.json"
    with open(plan_stats_path, "w") as f:
        json.dump(plan["statistics"], f, indent=2)

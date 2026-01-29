"""
CLI Entry Point for Plan Agent.
"""

import argparse
import json
import sys
from pathlib import Path

from . import PlanGenerator, validate_plan
from .output_generator import save_plan_outputs


def main():
    """Main entry point for the plan agent CLI."""
    parser = argparse.ArgumentParser(
        description="Plan Agent - Generate migration plans from transform outputs"
    )
    parser.add_argument(
        "--transform-output",
        required=True,
        help="Path to transform output JSON file",
    )
    parser.add_argument(
        "--project-id",
        required=True,
        help="Source project identifier",
    )
    parser.add_argument(
        "--run-id",
        required=True,
        help="Unique run identifier",
    )
    parser.add_argument(
        "--output-dir",
        default="./artifacts",
        help="Output directory for plan files (default: ./artifacts)",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Only validate the plan, do not save outputs",
    )
    
    args = parser.parse_args()
    
    # Load transform output
    try:
        with open(args.transform_output, "r") as f:
            transform_output = json.load(f)
    except FileNotFoundError:
        print(f"Error: Transform output file not found: {args.transform_output}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in transform output: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Generate plan
    try:
        print(f"Generating migration plan for project: {args.project_id}")
        print(f"Run ID: {args.run_id}")
        
        generator = PlanGenerator(args.project_id, args.run_id)
        plan = generator.generate_from_transform(transform_output)
        
        print(f"✓ Generated {plan['statistics']['total_actions']} actions")
        print(f"✓ Organized into {len([p for p in plan['phases'].values() if p])} phases")
        
        # Validate plan
        print("Validating plan...")
        validate_plan(plan)
        print("✓ Plan validation successful")
        
        if args.validate_only:
            print("Validation complete (--validate-only specified)")
            sys.exit(0)
        
        # Save outputs
        output_path = Path(args.output_dir) / args.run_id / "plan"
        print(f"Saving plan outputs to: {output_path}")
        
        save_plan_outputs(plan, output_path, generator.dependency_graph)
        
        print(f"✓ Saved plan.json")
        print(f"✓ Saved plan.md")
        print(f"✓ Saved dependency_graph.json")
        print(f"✓ Saved user_inputs_required.json")
        print(f"✓ Saved plan_stats.json")
        
        # Print summary
        print("\nPlan Summary:")
        print(f"  Total actions: {plan['statistics']['total_actions']}")
        print(f"  Actions requiring user input: {plan['statistics']['actions_requiring_user_input']}")
        print(f"  Total dependencies: {plan['statistics']['total_dependencies']}")
        
        print(f"\nPlan generated successfully: {output_path / 'plan.json'}")
        
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

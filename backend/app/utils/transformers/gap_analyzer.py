"""Gap analyzer for identifying migration limitations and unsupported features"""

from typing import Any, Dict, List, Optional
from .base_transformer import BaseTransformer, TransformationResult


class GapAnalyzer(BaseTransformer):
    """
    Analyze and document conversion gaps and limitations.
    
    Identifies:
    - Unsupported CI/CD features
    - Unmapped users
    - Missing data
    - Feature differences
    - Manual actions required
    """
    
    def __init__(self):
        super().__init__("GapAnalyzer")
        self.gaps: List[Dict[str, Any]] = []
    
    def transform(self, input_data: Dict[str, Any]) -> TransformationResult:
        """
        Analyze migration data and identify gaps.
        
        Args:
            input_data: Dict with:
                - 'cicd_gaps': List of CI/CD conversion gaps
                - 'user_mappings': User mapping results
                - 'gitlab_features': List of GitLab features used
                - 'github_limitations': Known GitHub limitations
            
        Returns:
            TransformationResult with gap analysis
        """
        self.log_transform_start("Gap Analysis")
        result = TransformationResult(success=True)
        
        try:
            self.gaps = []
            
            # Analyze CI/CD gaps
            if "cicd_gaps" in input_data:
                self._analyze_cicd_gaps(input_data["cicd_gaps"])
            
            # Analyze user mapping gaps
            if "user_mappings" in input_data:
                self._analyze_user_mapping_gaps(input_data["user_mappings"])
            
            # Analyze feature gaps
            if "gitlab_features" in input_data:
                self._analyze_feature_gaps(input_data["gitlab_features"])
            
            # Categorize gaps by severity
            categorized_gaps = self._categorize_gaps()
            
            # Generate action items
            action_items = self._generate_action_items()
            
            result.data = {
                "gaps": self.gaps,
                "categorized_gaps": categorized_gaps,
                "action_items": action_items,
                "summary": self._generate_summary(categorized_gaps)
            }
            
            result.metadata["total_gaps"] = len(self.gaps)
            result.metadata["critical_gaps"] = len(categorized_gaps.get("critical", []))
            result.metadata["action_items_count"] = len(action_items)
            
            # Add warnings for critical gaps
            if categorized_gaps.get("critical"):
                result.add_warning(
                    f"{len(categorized_gaps['critical'])} critical gaps require attention",
                    {"critical_gaps": [g["message"] for g in categorized_gaps["critical"]]}
                )
            
            self.log_transform_complete(True, f"Identified {len(self.gaps)} gaps")
            
        except Exception as e:
            result.add_error(f"Gap analysis error: {str(e)}")
            self.log_transform_complete(False, str(e))
        
        return result
    
    def add_gap(
        self,
        gap_type: str,
        message: str,
        severity: str = "medium",
        action: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """
        Add a gap to the analysis.
        
        Args:
            gap_type: Type of gap (cicd, user, feature, data, etc.)
            message: Description of the gap
            severity: critical, high, medium, low
            action: Recommended action to address the gap
            context: Additional context information
        """
        self.gaps.append({
            "type": gap_type,
            "message": message,
            "severity": severity,
            "action": action,
            "context": context or {}
        })
    
    def _analyze_cicd_gaps(self, cicd_gaps: List[Dict[str, Any]]):
        """Analyze CI/CD conversion gaps"""
        for gap in cicd_gaps:
            gap_type = gap.get("type", "cicd")
            
            # Determine severity based on gap type
            severity = "medium"
            if gap_type in ["runner_tags", "custom_executor"]:
                severity = "high"
            elif gap_type in ["schedule", "trigger"]:
                severity = "medium"
            
            self.add_gap(
                gap_type=f"cicd_{gap_type}",
                message=gap.get("message", "CI/CD conversion gap"),
                severity=severity,
                action=gap.get("action"),
                context=gap
            )
    
    def _analyze_user_mapping_gaps(self, user_mappings: Dict[str, Any]):
        """Analyze user mapping gaps"""
        stats = user_mappings.get("stats", {})
        unmapped_users = user_mappings.get("unmapped_users", [])
        
        unmapped_count = stats.get("unmapped", 0)
        low_confidence_count = stats.get("low_confidence", 0)
        
        if unmapped_count > 0:
            self.add_gap(
                gap_type="user_unmapped",
                message=f"{unmapped_count} users could not be mapped to GitHub accounts",
                severity="high" if unmapped_count > 5 else "medium",
                action="Review unmapped users and manually map them, or configure fallback strategy",
                context={
                    "unmapped_count": unmapped_count,
                    "unmapped_users": [u["gitlab"]["username"] for u in unmapped_users[:10]]  # First 10
                }
            )
        
        if low_confidence_count > 0:
            self.add_gap(
                gap_type="user_low_confidence",
                message=f"{low_confidence_count} users mapped with low confidence",
                severity="medium",
                action="Review low confidence mappings and confirm or adjust",
                context={"low_confidence_count": low_confidence_count}
            )
    
    def _analyze_feature_gaps(self, gitlab_features: List[str]):
        """Analyze GitLab-specific features that may not have GitHub equivalents"""
        
        # Known feature gaps
        feature_gaps = {
            "epic": {
                "message": "GitLab Epics are not directly supported in GitHub (use Projects or mega issues)",
                "severity": "medium",
                "action": "Convert epics to GitHub issues with epic label and link child issues"
            },
            "roadmap": {
                "message": "GitLab Roadmaps are not directly supported in GitHub",
                "severity": "low",
                "action": "Use GitHub Projects (beta) or create roadmap documentation"
            },
            "time_tracking": {
                "message": "GitLab time tracking is not natively supported in GitHub",
                "severity": "low",
                "action": "Use third-party integrations or track in issue comments"
            },
            "requirements": {
                "message": "GitLab Requirements Management not available in GitHub",
                "severity": "medium",
                "action": "Convert to issues with requirements label"
            },
            "compliance": {
                "message": "GitLab Compliance features differ from GitHub",
                "severity": "high",
                "action": "Review compliance requirements and configure GitHub equivalents"
            },
            "vulnerabilities": {
                "message": "GitLab Vulnerability tracking differs from GitHub Security",
                "severity": "medium",
                "action": "Enable GitHub Security features and review vulnerability reports"
            }
        }
        
        for feature in gitlab_features:
            if feature.lower() in feature_gaps:
                gap_info = feature_gaps[feature.lower()]
                self.add_gap(
                    gap_type=f"feature_{feature}",
                    message=gap_info["message"],
                    severity=gap_info["severity"],
                    action=gap_info["action"],
                    context={"feature": feature}
                )
    
    def _categorize_gaps(self) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize gaps by severity"""
        categorized = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": []
        }
        
        for gap in self.gaps:
            severity = gap.get("severity", "medium")
            if severity in categorized:
                categorized[severity].append(gap)
        
        return categorized
    
    def _generate_action_items(self) -> List[Dict[str, Any]]:
        """Generate prioritized action items from gaps"""
        action_items = []
        
        # Sort gaps by severity (critical first)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_gaps = sorted(
            self.gaps,
            key=lambda g: severity_order.get(g.get("severity", "medium"), 2)
        )
        
        for i, gap in enumerate(sorted_gaps):
            if gap.get("action"):
                action_items.append({
                    "priority": i + 1,
                    "severity": gap.get("severity"),
                    "type": gap.get("type"),
                    "action": gap.get("action"),
                    "message": gap.get("message"),
                    "context": gap.get("context", {})
                })
        
        return action_items
    
    def _generate_summary(self, categorized_gaps: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Generate summary of gap analysis"""
        return {
            "total_gaps": len(self.gaps),
            "by_severity": {
                severity: len(gaps)
                for severity, gaps in categorized_gaps.items()
            },
            "requires_manual_action": sum(
                1 for gap in self.gaps if gap.get("action")
            ),
            "critical_attention_needed": len(categorized_gaps.get("critical", [])) > 0
        }
    
    def generate_gap_report(self, categorized_gaps: Dict[str, List[Dict[str, Any]]]) -> str:
        """
        Generate a human-readable gap report.
        
        Args:
            categorized_gaps: Gaps categorized by severity
            
        Returns:
            Markdown formatted gap report
        """
        report_lines = ["# Migration Conversion Gaps Report\n"]
        
        # Summary
        report_lines.append("## Summary\n")
        total = sum(len(gaps) for gaps in categorized_gaps.values())
        report_lines.append(f"- **Total Gaps**: {total}")
        report_lines.append(f"- **Critical**: {len(categorized_gaps.get('critical', []))}")
        report_lines.append(f"- **High**: {len(categorized_gaps.get('high', []))}")
        report_lines.append(f"- **Medium**: {len(categorized_gaps.get('medium', []))}")
        report_lines.append(f"- **Low**: {len(categorized_gaps.get('low', []))}\n")
        
        # Detailed gaps by severity
        for severity in ["critical", "high", "medium", "low"]:
            gaps = categorized_gaps.get(severity, [])
            if gaps:
                report_lines.append(f"## {severity.upper()} Severity Gaps\n")
                
                for gap in gaps:
                    report_lines.append(f"### {gap.get('type', 'Unknown')}\n")
                    report_lines.append(f"**Message**: {gap.get('message')}\n")
                    
                    if gap.get("action"):
                        report_lines.append(f"**Action Required**: {gap['action']}\n")
                    
                    report_lines.append("")
        
        return "\n".join(report_lines)

"""
Pattern manager for runtime pattern management
"""

import re
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
import structlog

from .models import Pattern, PatternSet, PatternStats, PatternType, Severity
from .loader import PatternLoader

logger = structlog.get_logger(__name__)


class PatternManager:
    """
    Manages patterns at runtime with caching and validation
    Follows KISS principle with simple in-memory management
    """
    
    def __init__(self, patterns_dir: Optional[Path] = None):
        self.loader = PatternLoader(patterns_dir)
        self.patterns: Dict[str, Pattern] = {}
        self.pattern_sets: Dict[str, PatternSet] = {}
        self.compiled_patterns: Dict[str, re.Pattern] = {}
        self._stats_cache: Optional[PatternStats] = None
        
        # Load default patterns
        self._load_patterns()
    
    def _load_patterns(self) -> None:
        """Load patterns from files with fallback to defaults"""
        try:
            # Try to load from directory
            self.pattern_sets = self.loader.load_from_directory()
            
            # If no patterns loaded, create defaults
            if not self.pattern_sets:
                logger.info("no_patterns_found_creating_defaults")
                default_set = self.loader.create_default_patterns()
                self.pattern_sets[default_set.name] = default_set
            
            # Build pattern index
            self._rebuild_pattern_index()
            
        except Exception as e:
            logger.error("pattern_loading_failed", error=str(e))
            # Fallback to minimal default set
            default_set = self.loader.create_default_patterns()
            self.pattern_sets = {default_set.name: default_set}
            self._rebuild_pattern_index()
    
    def _rebuild_pattern_index(self) -> None:
        """Rebuild pattern index and compile regex patterns"""
        self.patterns.clear()
        self.compiled_patterns.clear()
        self._stats_cache = None
        
        for pattern_set in self.pattern_sets.values():
            for pattern in pattern_set.get_enabled_patterns():
                self.patterns[pattern.id] = pattern
                
                # Compile regex patterns
                if pattern.pattern_type == PatternType.REGEX:
                    try:
                        flags = 0 if pattern.case_sensitive else re.IGNORECASE
                        self.compiled_patterns[pattern.id] = re.compile(pattern.pattern, flags)
                    except re.error as e:
                        logger.error("pattern_compile_failed", 
                                   pattern_id=pattern.id, 
                                   pattern=pattern.pattern, 
                                   error=str(e))
        
        logger.info("patterns_indexed", total=len(self.patterns))
    
    def match_patterns(self, text: str) -> List[Dict[str, Any]]:
        """
        Match text against all enabled patterns
        Returns list of matches with pattern info
        """
        matches = []
        
        for pattern_id, pattern in self.patterns.items():
            match_info = self._match_single_pattern(text, pattern)
            if match_info:
                matches.append(match_info)
        
        return matches
    
    def _match_single_pattern(self, text: str, pattern: Pattern) -> Optional[Dict[str, Any]]:
        """Match text against a single pattern"""
        try:
            if pattern.pattern_type == PatternType.REGEX:
                compiled_pattern = self.compiled_patterns.get(pattern.id)
                if compiled_pattern and compiled_pattern.search(text):
                    return {
                        "pattern_id": pattern.id,
                        "pattern_name": pattern.name,
                        "category": pattern.category,
                        "severity": pattern.severity.value,
                        "risk_score": pattern.risk_score,
                        "description": pattern.description
                    }
            
            elif pattern.pattern_type == PatternType.SUBSTRING:
                search_text = text if pattern.case_sensitive else text.lower()
                search_pattern = pattern.pattern if pattern.case_sensitive else pattern.pattern.lower()
                if search_pattern in search_text:
                    return {
                        "pattern_id": pattern.id,
                        "pattern_name": pattern.name,
                        "category": pattern.category,
                        "severity": pattern.severity.value,
                        "risk_score": pattern.risk_score,
                        "description": pattern.description
                    }
            
            elif pattern.pattern_type == PatternType.KEYWORD:
                words = text.split() if pattern.case_sensitive else text.lower().split()
                keywords = pattern.pattern.split() if pattern.case_sensitive else pattern.pattern.lower().split()
                if any(keyword in words for keyword in keywords):
                    return {
                        "pattern_id": pattern.id,
                        "pattern_name": pattern.name,
                        "category": pattern.category,
                        "severity": pattern.severity.value,
                        "risk_score": pattern.risk_score,
                        "description": pattern.description
                    }
        
        except Exception as e:
            logger.error("pattern_match_error", 
                        pattern_id=pattern.id, 
                        error=str(e))
        
        return None
    
    def get_patterns_by_category(self, category: str) -> List[Pattern]:
        """Get patterns by category"""
        return [p for p in self.patterns.values() if p.category == category]
    
    def get_patterns_by_severity(self, severity: Severity) -> List[Pattern]:
        """Get patterns by severity"""
        return [p for p in self.patterns.values() if p.severity == severity]
    
    def get_pattern_stats(self) -> PatternStats:
        """Get pattern statistics"""
        if self._stats_cache is None:
            categories = {}
            severities = {}
            
            for pattern in self.patterns.values():
                categories[pattern.category] = categories.get(pattern.category, 0) + 1
                severities[pattern.severity.value] = severities.get(pattern.severity.value, 0) + 1
            
            self._stats_cache = PatternStats(
                total_patterns=len(self.patterns),
                enabled_patterns=len(self.patterns),  # Only enabled patterns are indexed
                patterns_by_category=categories,
                patterns_by_severity=severities,
                pattern_sets=list(self.pattern_sets.keys())
            )
        
        return self._stats_cache
    
    def add_pattern_set(self, pattern_set: PatternSet) -> None:
        """Add a new pattern set"""
        self.pattern_sets[pattern_set.name] = pattern_set
        self._rebuild_pattern_index()
        logger.info("pattern_set_added", name=pattern_set.name, patterns=len(pattern_set.patterns))
    
    def remove_pattern_set(self, name: str) -> bool:
        """Remove a pattern set"""
        if name in self.pattern_sets:
            del self.pattern_sets[name]
            self._rebuild_pattern_index()
            logger.info("pattern_set_removed", name=name)
            return True
        return False
    
    def reload_patterns(self) -> None:
        """Reload patterns from files"""
        logger.info("reloading_patterns")
        self._load_patterns()
    
    def add_pattern(self, pattern: Pattern, pattern_set_name: str = "runtime") -> bool:
        """Add a single pattern to a pattern set"""
        # Validate pattern first
        errors = self.validate_pattern(pattern)
        if errors:
            raise ValueError(f"Pattern validation failed: {'; '.join(errors)}")
        
        # Check for duplicate ID
        if pattern.id in self.patterns:
            raise ValueError(f"Pattern with ID '{pattern.id}' already exists")
        
        # Get or create pattern set
        if pattern_set_name not in self.pattern_sets:
            from .models import PatternSet
            self.pattern_sets[pattern_set_name] = PatternSet(
                name=pattern_set_name,
                version="1.0.0",
                description=f"Runtime pattern set: {pattern_set_name}",
                patterns=[]
            )
        
        # Add pattern to set
        self.pattern_sets[pattern_set_name].patterns.append(pattern)
        self._rebuild_pattern_index()
        
        logger.info("pattern_added", pattern_id=pattern.id, set_name=pattern_set_name)
        return True
    
    def update_pattern(self, pattern_id: str, updated_pattern: Pattern) -> bool:
        """Update an existing pattern"""
        if pattern_id not in self.patterns:
            return False
        
        # Validate updated pattern
        errors = self.validate_pattern(updated_pattern)
        if errors:
            raise ValueError(f"Pattern validation failed: {'; '.join(errors)}")
        
        # Ensure ID consistency
        updated_pattern.id = pattern_id
        
        # Find and update pattern in its set
        for pattern_set in self.pattern_sets.values():
            for i, pattern in enumerate(pattern_set.patterns):
                if pattern.id == pattern_id:
                    pattern_set.patterns[i] = updated_pattern
                    self._rebuild_pattern_index()
                    logger.info("pattern_updated", pattern_id=pattern_id)
                    return True
        
        return False
    
    def delete_pattern(self, pattern_id: str) -> bool:
        """Delete a pattern by ID"""
        if pattern_id not in self.patterns:
            return False
        
        # Find and remove pattern from its set
        for pattern_set in self.pattern_sets.values():
            pattern_set.patterns = [p for p in pattern_set.patterns if p.id != pattern_id]
        
        self._rebuild_pattern_index()
        logger.info("pattern_deleted", pattern_id=pattern_id)
        return True
    
    def get_pattern(self, pattern_id: str) -> Optional[Pattern]:
        """Get a single pattern by ID"""
        return self.patterns.get(pattern_id)
    
    def bulk_add_patterns(self, patterns: List[Pattern], pattern_set_name: str = "bulk") -> Dict[str, Any]:
        """Add multiple patterns in bulk"""
        results = {
            "added": [],
            "failed": [],
            "errors": []
        }
        
        # Validate all patterns first
        for pattern in patterns:
            try:
                errors = self.validate_pattern(pattern)
                if errors:
                    results["failed"].append(pattern.id)
                    results["errors"].append(f"{pattern.id}: {'; '.join(errors)}")
                    continue
                
                if pattern.id in self.patterns:
                    results["failed"].append(pattern.id)
                    results["errors"].append(f"{pattern.id}: Pattern ID already exists")
                    continue
                    
                results["added"].append(pattern.id)
                
            except Exception as e:
                results["failed"].append(pattern.id)
                results["errors"].append(f"{pattern.id}: {str(e)}")
        
        # Add valid patterns
        if results["added"]:
            # Get or create pattern set
            if pattern_set_name not in self.pattern_sets:
                from .models import PatternSet
                self.pattern_sets[pattern_set_name] = PatternSet(
                    name=pattern_set_name,
                    version="1.0.0",
                    description=f"Bulk imported pattern set: {pattern_set_name}",
                    patterns=[]
                )
            
            # Add patterns that passed validation
            valid_patterns = [p for p in patterns if p.id in results["added"]]
            self.pattern_sets[pattern_set_name].patterns.extend(valid_patterns)
            self._rebuild_pattern_index()
        
        logger.info("bulk_add_completed", 
                   added=len(results["added"]), 
                   failed=len(results["failed"]))
        
        return results
    
    def bulk_delete_patterns(self, pattern_ids: List[str]) -> Dict[str, Any]:
        """Delete multiple patterns in bulk"""
        results = {
            "deleted": [],
            "not_found": []
        }
        
        for pattern_id in pattern_ids:
            if self.delete_pattern(pattern_id):
                results["deleted"].append(pattern_id)
            else:
                results["not_found"].append(pattern_id)
        
        logger.info("bulk_delete_completed",
                   deleted=len(results["deleted"]),
                   not_found=len(results["not_found"]))
        
        return results
    
    def bulk_update_patterns(self, patterns: List[Pattern]) -> Dict[str, Any]:
        """Update multiple patterns in bulk"""
        results = {
            "updated": [],
            "failed": [],
            "errors": []
        }
        
        for pattern in patterns:
            try:
                if self.update_pattern(pattern.id, pattern):
                    results["updated"].append(pattern.id)
                else:
                    results["failed"].append(pattern.id)
                    results["errors"].append(f"{pattern.id}: Pattern not found")
            except Exception as e:
                results["failed"].append(pattern.id)
                results["errors"].append(f"{pattern.id}: {str(e)}")
        
        logger.info("bulk_update_completed",
                   updated=len(results["updated"]),
                   failed=len(results["failed"]))
        
        return results
    
    def enable_pattern(self, pattern_id: str) -> bool:
        """Enable a pattern"""
        pattern = self.get_pattern(pattern_id)
        if pattern:
            pattern.enabled = True
            self._rebuild_pattern_index()
            return True
        return False
    
    def disable_pattern(self, pattern_id: str) -> bool:
        """Disable a pattern"""
        if pattern_id in self.patterns:
            # Find pattern in sets and disable it
            for pattern_set in self.pattern_sets.values():
                for pattern in pattern_set.patterns:
                    if pattern.id == pattern_id:
                        pattern.enabled = False
                        self._rebuild_pattern_index()
                        return True
        return False
    
    def validate_pattern(self, pattern: Pattern) -> List[str]:
        """Validate a pattern and return any errors"""
        errors = []
        
        # Validate regex patterns
        if pattern.pattern_type == PatternType.REGEX:
            try:
                re.compile(pattern.pattern)
            except re.error as e:
                errors.append(f"Invalid regex pattern: {str(e)}")
        
        # Validate risk score
        if not (0 <= pattern.risk_score <= 100):
            errors.append("Risk score must be between 0 and 100")
        
        # Validate required fields
        if not pattern.pattern.strip():
            errors.append("Pattern cannot be empty")
        
        if not pattern.category.strip():
            errors.append("Category cannot be empty")
        
        # Validate ID format
        if not pattern.id or not pattern.id.strip():
            errors.append("Pattern ID cannot be empty")
        
        if not re.match(r'^[a-zA-Z0-9_-]+$', pattern.id):
            errors.append("Pattern ID can only contain letters, numbers, underscores, and hyphens")
        
        return errors
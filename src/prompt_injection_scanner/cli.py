"""
Command-line interface for the scanner
Simple, clean CLI following KISS principle
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Optional, List

import click
import structlog
import yaml

from .factory import create_scanner
from .config import get_config
from .vector_db.factory import create_vector_db

logger = structlog.get_logger(__name__)


def setup_logging(log_level: str = "INFO"):
    """Setup structured logging for CLI"""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


@click.group()
@click.option('--log-level', default="INFO", help="Log level (DEBUG, INFO, WARNING, ERROR)")
@click.option('--config-file', help="Configuration file path")
def cli(log_level: str, config_file: Optional[str]):
    """Prompt Injection Scanner CLI"""
    setup_logging(log_level)
    
    if config_file:
        # Would load custom config file here
        pass


@cli.command()
@click.argument('prompt', required=False)
@click.option('--file', '-f', help="Read prompt from file")
@click.option('--output', '-o', help="Output file for results (JSON)")
@click.option('--verbose', '-v', is_flag=True, help="Verbose output")
@click.option('--api-version', default="v1", help="API version to use (v1)")
@click.option('--include-reasoning', is_flag=True, help="Include detailed reasoning in output")
async def scan(prompt: Optional[str], file: Optional[str], output: Optional[str], verbose: bool, api_version: str, include_reasoning: bool):
    """Scan a prompt for injection attacks"""
    
    # Get prompt text
    if file:
        prompt_text = Path(file).read_text().strip()
    elif prompt:
        prompt_text = prompt
    else:
        # Read from stdin
        prompt_text = sys.stdin.read().strip()
    
    if not prompt_text:
        click.echo("Error: No prompt provided", err=True)
        sys.exit(1)
    
    # Create scanner and handler based on API version
    config = get_config()
    scanner = create_scanner()
    
    try:
        if api_version == "v1":
            from .api.v1.handlers import ScanHandlerV1
            from .api.v1.models import ScanRequest
            
            handler = ScanHandlerV1(scanner)
            request = ScanRequest(
                prompt=prompt_text,
                include_reasoning=include_reasoning
            )
            result = await handler.scan_prompt(request)
            
            # Format v1 output
            result_dict = {
                "risk_score": result.risk_score,
                "risk_level": result.risk_level.value,
                "confidence": result.confidence,
                "flags": result.flags,
                "threat_types": result.threat_types,
                "stage_results": [stage.model_dump() for stage in result.stage_results],
                "recommendations": result.recommendations,
                "request_id": result.request_id,
                "api_version": result.api_version
            }
            
            if include_reasoning and result.reasoning:
                result_dict["reasoning"] = result.reasoning
        else:
            # Fallback to core scanner
            result = await scanner.scan(prompt_text)
            result_dict = {
                "risk_score": result.risk_score,
                "confidence": result.confidence,
                "flags": result.flags,
                "stage_scores": result.stage_scores,
                "request_id": result.request_id,
                "api_version": "core"
            }
        
        if output:
            # Write to file
            Path(output).write_text(json.dumps(result_dict, indent=2))
            click.echo(f"Results written to {output}")
        else:
            # Print to stdout
            if verbose:
                click.echo(json.dumps(result_dict, indent=2))
            else:
                click.echo(f"Risk Score: {result_dict['risk_score']}")
                click.echo(f"Confidence: {result_dict['confidence']:.2f}")
                if result_dict.get('risk_level'):
                    click.echo(f"Risk Level: {result_dict['risk_level']}")
                if result_dict.get('flags'):
                    click.echo(f"Flags: {', '.join(result_dict['flags'])}")
                if result_dict.get('threat_types'):
                    click.echo(f"Threat Types: {', '.join(result_dict['threat_types'])}")
                if result_dict.get('recommendations') and not verbose:
                    click.echo(f"Recommendations: {len(result_dict['recommendations'])} available (use -v for details)")
                if result_dict.get('reasoning') and include_reasoning:
                    click.echo(f"Reasoning: {result_dict['reasoning']}")
    
    except Exception as e:
        logger.error("scan_failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--input', '-i', required=True, help="Input file (JSONL format)")
@click.option('--output', '-o', required=True, help="Output file (JSONL format)")
@click.option('--workers', '-w', default=5, help="Number of concurrent workers")
async def batch(input: str, output: str, workers: int):
    """Process multiple prompts from JSONL file"""
    
    input_path = Path(input)
    output_path = Path(output)
    
    if not input_path.exists():
        click.echo(f"Error: Input file {input} does not exist", err=True)
        sys.exit(1)
    
    # Create scanner
    scanner = create_scanner()
    
    # Process batch
    results = []
    processed = 0
    
    try:
        with input_path.open() as f:
            lines = f.readlines()
        
        click.echo(f"Processing {len(lines)} prompts with {workers} workers...")
        
        # Process in batches
        semaphore = asyncio.Semaphore(workers)
        
        async def process_line(line: str) -> dict:
            async with semaphore:
                try:
                    data = json.loads(line.strip())
                    prompt_text = data.get('prompt', '')
                    
                    if not prompt_text:
                        return {"error": "No prompt provided"}
                    
                    result = await scanner.scan(prompt_text)
                    return {
                        "input": data,
                        "result": {
                            "risk_score": result.risk_score,
                            "confidence": result.confidence,
                            "flags": result.flags,
                            "stage_scores": result.stage_scores,
                            "request_id": result.request_id
                        }
                    }
                except Exception as e:
                    return {"input": data if 'data' in locals() else {}, "error": str(e)}
        
        # Process all lines concurrently
        tasks = [process_line(line) for line in lines]
        results = await asyncio.gather(*tasks)
        
        # Write results
        with output_path.open('w') as f:
            for result in results:
                f.write(json.dumps(result) + '\n')
        
        click.echo(f"Processed {len(results)} prompts. Results written to {output}")
        
    except Exception as e:
        logger.error("batch_processing_failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.command()
async def serve():
    """Start the FastAPI server"""
    import uvicorn
    from .main import app
    
    config = get_config()
    
    click.echo(f"Starting server on {config.host}:{config.port}")
    
    uvicorn.run(
        app,
        host=config.host,
        port=config.port,
        log_level=config.log_level.lower()
    )


@cli.command()
@click.option('--db-type', default="memory", help="Vector DB type (memory, chromadb)")
@click.option('--url', help="Vector database URL")
async def seed_db(db_type: str, url: Optional[str]):
    """Seed vector database with default attack patterns"""
    
    from .vector_db.factory import seed_default_attacks
    from .stages.vector import VectorStage
    
    # Create vector database
    vector_db = create_vector_db(db_type, url)
    
    # Create embedding function
    vector_stage = VectorStage()
    
    try:
        await seed_default_attacks(vector_db, vector_stage._get_embedding)
        click.echo("Vector database seeded successfully")
    except Exception as e:
        logger.error("seeding_failed", error=str(e))
        click.echo(f"Error seeding database: {e}", err=True)
        sys.exit(1)
    finally:
        await vector_db.close()


@cli.command()
def config():
    """Show current configuration"""
    config = get_config()
    click.echo(json.dumps(config.model_dump(), indent=2))


@cli.group()
def patterns():
    """Pattern management commands"""
    pass


@patterns.command("list")
@click.option('--category', help="Filter by category")
@click.option('--severity', help="Filter by severity")
@click.option('--format', 'output_format', default="table", help="Output format (table, json)")
async def list_patterns(category: Optional[str], severity: Optional[str], output_format: str):
    """List configured patterns"""
    from .patterns import PatternManager
    
    try:
        pattern_manager = PatternManager()
        patterns = list(pattern_manager.patterns.values())
        
        # Apply filters
        if category:
            patterns = [p for p in patterns if p.category == category]
        
        if severity:
            patterns = [p for p in patterns if p.severity.value == severity]
        
        if output_format == "json":
            data = {
                "patterns": [p.model_dump() for p in patterns],
                "total": len(patterns)
            }
            click.echo(json.dumps(data, indent=2))
        else:
            # Table format
            click.echo(f"{'ID':<20} {'Name':<25} {'Category':<15} {'Severity':<10} {'Risk':<5} {'Enabled':<8}")
            click.echo("-" * 90)
            for pattern in patterns:
                click.echo(f"{pattern.id:<20} {pattern.name:<25} {pattern.category:<15} "
                          f"{pattern.severity.value:<10} {pattern.risk_score:<5} {pattern.enabled:<8}")
            
            click.echo(f"\nTotal: {len(patterns)} patterns")
    
    except Exception as e:
        logger.error("list_patterns_failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@patterns.command("stats")
async def pattern_stats():
    """Show pattern statistics"""
    from .patterns import PatternManager
    
    try:
        pattern_manager = PatternManager()
        stats = pattern_manager.get_pattern_stats()
        
        click.echo("Pattern Statistics:")
        click.echo(f"  Total Patterns: {stats.total_patterns}")
        click.echo(f"  Enabled Patterns: {stats.enabled_patterns}")
        click.echo(f"  Pattern Sets: {len(stats.pattern_sets)}")
        
        click.echo("\nBy Category:")
        for category, count in stats.patterns_by_category.items():
            click.echo(f"  {category}: {count}")
        
        click.echo("\nBy Severity:")
        for severity, count in stats.patterns_by_severity.items():
            click.echo(f"  {severity}: {count}")
        
        click.echo(f"\nPattern Sets: {', '.join(stats.pattern_sets)}")
    
    except Exception as e:
        logger.error("pattern_stats_failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@patterns.command("test")
@click.argument('text')
@click.option('--verbose', '-v', is_flag=True, help="Show detailed match information")
async def test_patterns(text: str, verbose: bool):
    """Test text against current patterns"""
    from .patterns import PatternManager
    
    try:
        pattern_manager = PatternManager()
        matches = pattern_manager.match_patterns(text)
        
        if not matches:
            click.echo("No patterns matched")
            return
        
        total_risk = sum(match.get("risk_score", 0) for match in matches)
        
        click.echo(f"Text: {text}")
        click.echo(f"Matches: {len(matches)}")
        click.echo(f"Total Risk Score: {total_risk}")
        
        if verbose:
            click.echo("\nDetailed Matches:")
            for match in matches:
                click.echo(f"  - {match['pattern_name']} ({match['pattern_id']})")
                click.echo(f"    Category: {match['category']}")
                click.echo(f"    Severity: {match['severity']}")
                click.echo(f"    Risk Score: {match['risk_score']}")
                click.echo(f"    Description: {match['description']}")
                click.echo()
        else:
            flags = [match['pattern_id'] for match in matches]
            categories = list(set(match['category'] for match in matches))
            click.echo(f"Flags: {', '.join(flags)}")
            click.echo(f"Categories: {', '.join(categories)}")
    
    except Exception as e:
        logger.error("test_patterns_failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@patterns.command("reload")
async def reload_patterns():
    """Reload patterns from configuration files"""
    from .patterns import PatternManager
    
    try:
        pattern_manager = PatternManager()
        old_count = len(pattern_manager.patterns)
        
        pattern_manager.reload_patterns()
        new_count = len(pattern_manager.patterns)
        
        click.echo(f"Patterns reloaded: {old_count} -> {new_count}")
        
        if new_count != old_count:
            click.echo(f"Pattern count changed by {new_count - old_count}")
    
    except Exception as e:
        logger.error("reload_patterns_failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@patterns.command("export")
@click.argument('output_file')
@click.option('--format', 'output_format', default="yaml", help="Output format (yaml, json)")
@click.option('--set-name', help="Export specific pattern set")
async def export_patterns(output_file: str, output_format: str, set_name: Optional[str]):
    """Export patterns to file"""
    from .patterns import PatternManager
    
    try:
        pattern_manager = PatternManager()
        
        if set_name:
            if set_name not in pattern_manager.pattern_sets:
                click.echo(f"Pattern set '{set_name}' not found", err=True)
                sys.exit(1)
            
            pattern_set = pattern_manager.pattern_sets[set_name]
        else:
            # Export all patterns as a combined set
            all_patterns = list(pattern_manager.patterns.values())
            from .patterns.models import PatternSet
            pattern_set = PatternSet(
                name="exported",
                version="1.0.0",
                description="Exported patterns",
                patterns=all_patterns
            )
        
        output_path = Path(output_file)
        pattern_manager.loader.save_pattern_set(pattern_set, output_path)
        
        click.echo(f"Patterns exported to {output_file}")
        click.echo(f"Pattern set: {pattern_set.name}")
        click.echo(f"Patterns: {len(pattern_set.patterns)}")
    
    except Exception as e:
        logger.error("export_patterns_failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@patterns.command("add")
@click.option('--id', 'pattern_id', required=True, help="Pattern ID")
@click.option('--name', required=True, help="Pattern name")
@click.option('--pattern', required=True, help="Pattern (regex, substring, etc.)")
@click.option('--type', 'pattern_type', default="regex", help="Pattern type (regex, substring, keyword)")
@click.option('--category', required=True, help="Pattern category")
@click.option('--severity', default="medium", help="Severity (low, medium, high, critical)")
@click.option('--risk-score', type=int, default=25, help="Risk score (0-100)")
@click.option('--description', help="Pattern description")
@click.option('--set-name', default="runtime", help="Pattern set name")
async def add_pattern(pattern_id: str, name: str, pattern: str, pattern_type: str, 
                     category: str, severity: str, risk_score: int, 
                     description: Optional[str], set_name: str):
    """Add a new pattern"""
    from .patterns import PatternManager
    from .patterns.models import Pattern, PatternType, Severity
    
    try:
        pattern_manager = PatternManager()
        
        # Create pattern object
        new_pattern = Pattern(
            id=pattern_id,
            name=name,
            description=description or f"Pattern: {name}",
            pattern=pattern,
            pattern_type=PatternType(pattern_type),
            severity=Severity(severity),
            category=category,
            risk_score=risk_score,
            enabled=True
        )
        
        # Add pattern
        pattern_manager.add_pattern(new_pattern, set_name)
        
        click.echo(f"Pattern '{pattern_id}' added successfully")
        click.echo(f"  Name: {name}")
        click.echo(f"  Category: {category}")
        click.echo(f"  Severity: {severity}")
        click.echo(f"  Risk Score: {risk_score}")
        click.echo(f"  Pattern Set: {set_name}")
    
    except Exception as e:
        logger.error("add_pattern_failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@patterns.command("update")
@click.argument('pattern_id')
@click.option('--name', help="Pattern name")
@click.option('--pattern', help="Pattern (regex, substring, etc.)")
@click.option('--type', 'pattern_type', help="Pattern type (regex, substring, keyword)")
@click.option('--category', help="Pattern category")
@click.option('--severity', help="Severity (low, medium, high, critical)")
@click.option('--risk-score', type=int, help="Risk score (0-100)")
@click.option('--description', help="Pattern description")
@click.option('--enabled/--disabled', default=None, help="Enable/disable pattern")
async def update_pattern(pattern_id: str, name: Optional[str], pattern: Optional[str],
                        pattern_type: Optional[str], category: Optional[str], 
                        severity: Optional[str], risk_score: Optional[int],
                        description: Optional[str], enabled: Optional[bool]):
    """Update an existing pattern"""
    from .patterns import PatternManager
    from .patterns.models import PatternType, Severity
    
    try:
        pattern_manager = PatternManager()
        
        # Get existing pattern
        existing_pattern = pattern_manager.get_pattern(pattern_id)
        if not existing_pattern:
            click.echo(f"Pattern '{pattern_id}' not found", err=True)
            sys.exit(1)
        
        # Update fields
        if name:
            existing_pattern.name = name
        if pattern:
            existing_pattern.pattern = pattern
        if pattern_type:
            existing_pattern.pattern_type = PatternType(pattern_type)
        if category:
            existing_pattern.category = category
        if severity:
            existing_pattern.severity = Severity(severity)
        if risk_score is not None:
            existing_pattern.risk_score = risk_score
        if description:
            existing_pattern.description = description
        if enabled is not None:
            existing_pattern.enabled = enabled
        
        # Update pattern
        pattern_manager.update_pattern(pattern_id, existing_pattern)
        
        click.echo(f"Pattern '{pattern_id}' updated successfully")
    
    except Exception as e:
        logger.error("update_pattern_failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@patterns.command("delete")
@click.argument('pattern_id')
@click.option('--confirm', is_flag=True, help="Skip confirmation prompt")
async def delete_pattern(pattern_id: str, confirm: bool):
    """Delete a pattern"""
    from .patterns import PatternManager
    
    try:
        pattern_manager = PatternManager()
        
        # Check if pattern exists
        existing_pattern = pattern_manager.get_pattern(pattern_id)
        if not existing_pattern:
            click.echo(f"Pattern '{pattern_id}' not found", err=True)
            sys.exit(1)
        
        # Confirm deletion
        if not confirm:
            click.echo(f"Pattern to delete:")
            click.echo(f"  ID: {existing_pattern.id}")
            click.echo(f"  Name: {existing_pattern.name}")
            click.echo(f"  Category: {existing_pattern.category}")
            
            if not click.confirm("Are you sure you want to delete this pattern?"):
                click.echo("Deletion cancelled")
                return
        
        # Delete pattern
        pattern_manager.delete_pattern(pattern_id)
        
        click.echo(f"Pattern '{pattern_id}' deleted successfully")
    
    except Exception as e:
        logger.error("delete_pattern_failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@patterns.command("get")
@click.argument('pattern_id')
async def get_pattern(pattern_id: str):
    """Get details of a specific pattern"""
    from .patterns import PatternManager
    
    try:
        pattern_manager = PatternManager()
        
        pattern = pattern_manager.get_pattern(pattern_id)
        if not pattern:
            click.echo(f"Pattern '{pattern_id}' not found", err=True)
            sys.exit(1)
        
        click.echo(f"Pattern Details:")
        click.echo(f"  ID: {pattern.id}")
        click.echo(f"  Name: {pattern.name}")
        click.echo(f"  Description: {pattern.description}")
        click.echo(f"  Pattern: {pattern.pattern}")
        click.echo(f"  Type: {pattern.pattern_type.value}")
        click.echo(f"  Category: {pattern.category}")
        click.echo(f"  Severity: {pattern.severity.value}")
        click.echo(f"  Risk Score: {pattern.risk_score}")
        click.echo(f"  Enabled: {pattern.enabled}")
        click.echo(f"  Case Sensitive: {pattern.case_sensitive}")
        
        if pattern.tags:
            click.echo(f"  Tags: {', '.join(pattern.tags)}")
        
        if pattern.examples:
            click.echo(f"  Examples:")
            for example in pattern.examples:
                click.echo(f"    - {example}")
    
    except Exception as e:
        logger.error("get_pattern_failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@patterns.command("enable")
@click.argument('pattern_id')
async def enable_pattern(pattern_id: str):
    """Enable a pattern"""
    from .patterns import PatternManager
    
    try:
        pattern_manager = PatternManager()
        
        if pattern_manager.enable_pattern(pattern_id):
            click.echo(f"Pattern '{pattern_id}' enabled successfully")
        else:
            click.echo(f"Pattern '{pattern_id}' not found", err=True)
            sys.exit(1)
    
    except Exception as e:
        logger.error("enable_pattern_failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@patterns.command("disable")
@click.argument('pattern_id')
async def disable_pattern(pattern_id: str):
    """Disable a pattern"""
    from .patterns import PatternManager
    
    try:
        pattern_manager = PatternManager()
        
        if pattern_manager.disable_pattern(pattern_id):
            click.echo(f"Pattern '{pattern_id}' disabled successfully")
        else:
            click.echo(f"Pattern '{pattern_id}' not found", err=True)
            sys.exit(1)
    
    except Exception as e:
        logger.error("disable_pattern_failed", error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@patterns.command("upload")
@click.argument('file_path')
@click.option('--set-name', help="Pattern set name (defaults to filename or file's name field)")
@click.option('--merge/--replace', default=True, help="Merge with existing patterns or replace")
async def upload_pattern_file(file_path: str, set_name: Optional[str], merge: bool):
    """Upload a pattern file (JSON or YAML)"""
    import yaml
    from .patterns import PatternManager
    from .patterns.models import PatternSet
    
    try:
        pattern_manager = PatternManager()
        file_path_obj = Path(file_path)
        
        # Check if file exists
        if not file_path_obj.exists():
            click.echo(f"File not found: {file_path}", err=True)
            sys.exit(1)
        
        # Validate file extension
        file_extension = file_path_obj.suffix.lower()
        if file_extension not in ['.json', '.yaml', '.yml']:
            click.echo(f"Unsupported file type: {file_extension}. Supported: .json, .yaml, .yml", err=True)
            sys.exit(1)
        
        # Read and parse file
        content = file_path_obj.read_text(encoding='utf-8')
        
        try:
            if file_extension == '.json':
                data = json.loads(content)
            else:  # .yaml or .yml
                data = yaml.safe_load(content)
        except (json.JSONDecodeError, yaml.YAMLError) as e:
            click.echo(f"Invalid file format: {str(e)}", err=True)
            sys.exit(1)
        
        # Validate and create pattern set
        try:
            pattern_set = PatternSet(**data)
        except Exception as e:
            click.echo(f"Invalid pattern set format: {str(e)}", err=True)
            sys.exit(1)
        
        # Use provided name or fall back to file name or pattern set name
        final_name = set_name or pattern_set.name or file_path_obj.stem
        pattern_set.name = final_name
        
        # Validate all patterns
        validation_errors = []
        for pattern in pattern_set.patterns:
            errors = pattern_manager.validate_pattern(pattern)
            if errors:
                validation_errors.extend([f"Pattern {pattern.id}: {error}" for error in errors])
        
        if validation_errors:
            click.echo("Pattern validation failed:", err=True)
            for error in validation_errors[:10]:  # Show first 10 errors
                click.echo(f"  - {error}", err=True)
            sys.exit(1)
        
        # Check for conflicts if not merging
        conflicts = []
        if not merge:
            for pattern in pattern_set.patterns:
                if pattern.id in pattern_manager.patterns:
                    conflicts.append(pattern.id)
        
        if conflicts:
            click.echo("Pattern conflicts found (use --merge to merge with existing):", err=True)
            for conflict in conflicts[:10]:  # Show first 10 conflicts
                click.echo(f"  - {conflict}", err=True)
            sys.exit(1)
        
        # Upload pattern set
        if merge and final_name in pattern_manager.pattern_sets:
            # Merge with existing set
            existing_set = pattern_manager.pattern_sets[final_name]
            
            added_patterns = []
            skipped_patterns = []
            
            for pattern in pattern_set.patterns:
                if pattern.id not in pattern_manager.patterns:
                    existing_set.patterns.append(pattern)
                    added_patterns.append(pattern.id)
                else:
                    skipped_patterns.append(pattern.id)
            
            pattern_manager._rebuild_pattern_index()
            
            click.echo(f"Pattern file merged successfully:")
            click.echo(f"  File: {file_path}")
            click.echo(f"  Pattern Set: {final_name}")
            click.echo(f"  Total in file: {len(pattern_set.patterns)}")
            click.echo(f"  Added: {len(added_patterns)}")
            click.echo(f"  Skipped (duplicates): {len(skipped_patterns)}")
            
            if added_patterns and len(added_patterns) <= 10:
                click.echo(f"  Added patterns: {', '.join(added_patterns)}")
        else:
            # Add as new pattern set or replace existing
            pattern_manager.add_pattern_set(pattern_set)
            
            click.echo(f"Pattern file uploaded successfully:")
            click.echo(f"  File: {file_path}")
            click.echo(f"  Pattern Set: {final_name}")
            click.echo(f"  Total patterns: {len(pattern_set.patterns)}")
            click.echo(f"  Enabled patterns: {len(pattern_set.get_enabled_patterns())}")
    
    except Exception as e:
        logger.error("upload_pattern_file_failed", file_path=file_path, error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@patterns.command("upload-bulk")
@click.argument('file_pattern')
@click.option('--set-name', help="Pattern set name prefix for bulk upload")
@click.option('--merge/--replace', default=True, help="Merge with existing patterns or replace")
async def upload_bulk_pattern_files(file_pattern: str, set_name: Optional[str], merge: bool):
    """Upload multiple pattern files using glob pattern"""
    import glob
    import yaml
    from .patterns import PatternManager
    from .patterns.models import PatternSet
    
    try:
        pattern_manager = PatternManager()
        
        # Find matching files
        file_paths = glob.glob(file_pattern)
        if not file_paths:
            click.echo(f"No files found matching pattern: {file_pattern}", err=True)
            sys.exit(1)
        
        results = {
            "uploaded": [],
            "failed": [],
            "errors": []
        }
        
        click.echo(f"Found {len(file_paths)} files to process...")
        
        for file_path in file_paths:
            try:
                file_path_obj = Path(file_path)
                
                # Validate file extension
                file_extension = file_path_obj.suffix.lower()
                if file_extension not in ['.json', '.yaml', '.yml']:
                    results["failed"].append(file_path)
                    results["errors"].append(f"{file_path}: Unsupported file type")
                    continue
                
                # Read and parse file
                content = file_path_obj.read_text(encoding='utf-8')
                
                try:
                    if file_extension == '.json':
                        data = json.loads(content)
                    else:  # .yaml or .yml
                        data = yaml.safe_load(content)
                except (json.JSONDecodeError, yaml.YAMLError) as e:
                    results["failed"].append(file_path)
                    results["errors"].append(f"{file_path}: Invalid file format - {str(e)}")
                    continue
                
                # Validate and create pattern set
                try:
                    pattern_set = PatternSet(**data)
                except Exception as e:
                    results["failed"].append(file_path)
                    results["errors"].append(f"{file_path}: Invalid pattern set format - {str(e)}")
                    continue
                
                # Use provided name prefix or fall back to individual file names
                if set_name:
                    final_name = f"{set_name}_{file_path_obj.stem}"
                else:
                    final_name = pattern_set.name or file_path_obj.stem
                
                pattern_set.name = final_name
                
                # Validate all patterns
                validation_errors = []
                for pattern in pattern_set.patterns:
                    errors = pattern_manager.validate_pattern(pattern)
                    if errors:
                        validation_errors.extend([f"Pattern {pattern.id}: {error}" for error in errors])
                
                if validation_errors:
                    results["failed"].append(file_path)
                    results["errors"].append(f"{file_path}: Pattern validation failed - {'; '.join(validation_errors[:3])}")
                    continue
                
                # Upload pattern set
                pattern_manager.add_pattern_set(pattern_set)
                results["uploaded"].append({
                    "file_path": file_path,
                    "pattern_set": final_name,
                    "patterns": len(pattern_set.patterns)
                })
                
            except Exception as e:
                results["failed"].append(file_path)
                results["errors"].append(f"{file_path}: {str(e)}")
        
        # Display results
        click.echo("\nBulk upload completed:")
        click.echo(f"  Total files: {len(file_paths)}")
        click.echo(f"  Successful: {len(results['uploaded'])}")
        click.echo(f"  Failed: {len(results['failed'])}")
        
        if results["uploaded"]:
            click.echo("\nSuccessfully uploaded:")
            total_patterns = 0
            for upload in results["uploaded"]:
                click.echo(f"  - {upload['file_path']} -> {upload['pattern_set']} ({upload['patterns']} patterns)")
                total_patterns += upload["patterns"]
            click.echo(f"  Total patterns added: {total_patterns}")
        
        if results["failed"]:
            click.echo("\nFailed uploads:")
            for i, error in enumerate(results["errors"]):
                click.echo(f"  - {error}")
                if i >= 9:  # Limit to first 10 errors
                    remaining = len(results["errors"]) - 10
                    if remaining > 0:
                        click.echo(f"  ... and {remaining} more errors")
                    break
    
    except Exception as e:
        logger.error("upload_bulk_pattern_files_failed", pattern=file_pattern, error=str(e))
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def run_async_command(coro):
    """Helper to run async commands"""
    asyncio.run(coro)


# Make async commands work with click
async_commands = [
    scan, batch, serve, seed_db, list_patterns, pattern_stats, test_patterns, 
    reload_patterns, export_patterns, add_pattern, update_pattern, delete_pattern, 
    get_pattern, enable_pattern, disable_pattern, upload_pattern_file, upload_bulk_pattern_files
]
for command in async_commands:
    command.callback = lambda *args, **kwargs, cmd=command.callback: run_async_command(cmd(*args, **kwargs))


if __name__ == '__main__':
    cli()
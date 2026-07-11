"""
Utility functions for discovering and running seed commands.
"""
import os
import importlib
from django.core.management import call_command
from django.core.management.base import CommandError
from django.apps import apps
from io import StringIO
from typing import List, Dict, Tuple, Optional, Any

from django.http import HttpRequest


def get_request_tenant_schema_name(request: Optional[HttpRequest]) -> str:
    """
    Schema to use when running seeds from Django admin.

    Prefer the tenant resolved by django-tenants middleware; fall back to the
    current DB connection schema (may be ``public``).
    """
    from django.db import connection

    if request is not None:
        tenant = getattr(request, "tenant", None)
        if tenant is not None and getattr(tenant, "schema_name", None):
            return tenant.schema_name
    return connection.schema_name


def discover_seed_commands() -> List[Dict[str, str]]:
    """
    Automatically discover all seed commands in the project.
    
    Returns a list of dictionaries with command information:
    [
        {
            'command': 'seed_roles',
            'app': 'authentication',
            'description': 'Seed default user roles',
            'path': 'authentication/management/commands/seed_roles.py'
        },
        ...
    ]
    """
    seed_commands = []
    
    # Get all installed apps
    installed_apps = apps.get_app_configs()
    
    for app_config in installed_apps:
        app_name = app_config.name
        app_path = app_config.path
        
        # Check for management/commands directory
        commands_dir = os.path.join(app_path, 'management', 'commands')
        
        if not os.path.exists(commands_dir):
            continue
        
        # Look for Python files that start with 'seed_' or contain 'seed' in the name
        try:
            command_files = [
                f for f in os.listdir(commands_dir)
                if f.endswith('.py') and not f.startswith('__')
                and ('seed' in f.lower() or 'populate' in f.lower())
            ]
            
            for command_file in command_files:
                command_name = command_file.replace('.py', '')
                
                # Try to get command help text
                try:
                    module_path = f"{app_name}.management.commands.{command_name}"
                    module = importlib.import_module(module_path)
                    
                    if hasattr(module, 'Command'):
                        command_class = module.Command
                        description = getattr(command_class, 'help', 'No description available')
                        
                        # Verify the command can be loaded by Django
                        try:
                            from django.core.management import get_commands
                            # This will raise an exception if command is invalid
                            get_commands().get(command_name)
                        except Exception:
                            # Command exists but might not be registered yet
                            # This is okay, we'll still include it
                            pass
                        
                        seed_commands.append({
                            'command': command_name,
                            'app': app_name,
                            'description': description,
                            'path': f"{app_name}/management/commands/{command_file}",
                        })
                except (ImportError, AttributeError, Exception) as e:
                    # Skip if we can't import or doesn't have Command class
                    # Log the error for debugging but continue
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.debug(f"Could not load command {command_name} from {app_name}: {e}")
                    continue
                    
        except OSError:
            # Skip if directory doesn't exist or can't be read
            continue
    
    # Sort by app name, then command name
    seed_commands.sort(key=lambda x: (x['app'], x['command']))
    
    return seed_commands


def run_seed_command(command_name: str, app_name: str = None, **kwargs) -> Tuple[bool, str]:
    """
    Run a single seed command.
    
    Always uses ``call_command`` so behavior matches the CLI and Django sets up
    the command stack correctly (nested ``call_command`` inside seeds, checks, etc.).
    ``app_name`` is retained for API compatibility only.

    Args:
        command_name: Name of the command to run (e.g., 'seed_roles')
        app_name: Optional app name (unused; kept for callers)
        **kwargs: Additional arguments to pass to the command
    
    Returns:
        Tuple of (success: bool, output: str)
    """
    output = StringIO()
    error_output = StringIO()
    
    try:
        call_command(
            command_name,
            stdout=output,
            stderr=error_output,
            **kwargs
        )
        success = True
        result = output.getvalue()
        
        if error_output.getvalue():
            result += f"\nWarnings:\n{error_output.getvalue()}"
            
    except CommandError as e:
        success = False
        error_msg = str(e)
        if "Unknown command" in error_msg:
            # Try to provide more helpful error message
            result = f"Error: Command '{command_name}' not found. This may require restarting the Django server to reload commands.\nOriginal error: {error_msg}\n{error_output.getvalue()}"
        else:
            result = f"Error: {error_msg}\n{error_output.getvalue()}"
    except Exception as e:
        success = False
        result = f"Unexpected error: {str(e)}\n{error_output.getvalue()}"
    
    return success, result


def run_all_seed_commands(**kwargs) -> Dict[str, Dict[str, Any]]:
    """
    Run all discovered seed commands.
    
    Args:
        schema_name: Optional tenant schema; when set, all commands run inside
            ``schema_context(schema_name)`` (e.g. from Seed Manager on a tenant host).
        **kwargs: Additional arguments to pass to each command
    
    Returns:
        Dictionary with results for each command:
        {
            'seed_roles': {
                'success': True,
                'output': '...',
                'app': 'authentication'
            },
            ...
        }
    """
    schema_name = kwargs.pop("schema_name", None)

    def _run_all() -> Dict[str, Dict[str, Any]]:
        commands = discover_seed_commands()
        results = {}
        for cmd_info in commands:
            command_name = cmd_info["command"]
            app_name = cmd_info["app"]
            success, output = run_seed_command(command_name, app_name, **kwargs)
            results[command_name] = {
                "success": success,
                "output": output,
                "app": app_name,
                "description": cmd_info["description"],
            }
        return results

    if schema_name:
        from django_tenants.utils import schema_context

        with schema_context(schema_name):
            return _run_all()
    return _run_all()


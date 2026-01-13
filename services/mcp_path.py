"""
MCP Path Utility - Centralized MCP path resolution.

Provides a single source of truth for finding the MCP directory,
which can be configured via environment variable or uses sensible defaults.
"""

import os
from pathlib import Path


def get_mcp_path() -> Path:
    """
    Get the MCP directory path.
    
    Priority:
    1. MCP_PATH environment variable
    2. ~/MCP (default)
    3. /Users/danielbadygov/MCP (fallback for local dev)
    """
    # Try environment variable first
    if os.getenv("MCP_PATH"):
        return Path(os.getenv("MCP_PATH"))
    
    # Check home directory
    home_mcp = Path.home() / "MCP"
    if home_mcp.exists():
        return home_mcp
    
    # Fallback to development path
    dev_path = Path("/Users/danielbadygov/MCP")
    if dev_path.exists():
        return dev_path
    
    # Return home path as last resort
    return home_mcp


def get_shared_module_path() -> str:
    """Get the shared module path for Python imports."""
    mcp_path = get_mcp_path()
    return str(mcp_path / "shared")


# Convenience function for use in other modules
def setup_python_path() -> None:
    """Add MCP paths to sys.path if needed."""
    import sys
    
    mcp_path = get_mcp_path()
    shared_path = get_shared_module_path()
    
    if str(mcp_path) not in sys.path:
        sys.path.insert(0, str(mcp_path))
    
    if shared_path not in sys.path:
        sys.path.insert(0, shared_path)


if __name__ == "__main__":
    mcp = get_mcp_path()
    print(f"MCP Path: {mcp}")
    print(f"Exists: {mcp.exists()}")

"""YAML utilities for project_creator_core.

Provides YamlFile and YamlReader for YAML operations. This is an inlined
version of yaml_reading_core, consolidated here during P3 module cleanup.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml


class YamlFile:
    """Represents a loaded YAML file with convenient data access methods."""
    
    def __init__(self, data: Dict[str, Any] | None = None, file_path: Union[str, Path] | None = None):
        self.data = data or {}
        self.file_path = file_path
    
    def exists_key(self, key_path: str) -> bool:
        """Check if a key exists using dot notation."""
        try:
            keys = key_path.split('.')
            value = self.data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return False
            return True
        except (AttributeError, TypeError):
            return False
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """Get a value using dot notation (e.g., 'section.key')."""
        try:
            keys = key_path.split('.')
            value = self.data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return default
            return value
        except (AttributeError, TypeError):
            return default
    
    def set(self, key_path: str, value: Any) -> None:
        """Set a value using dot notation, creating intermediate dicts as needed."""
        try:
            keys = key_path.split('.')
            current = self.data
            
            # Navigate to the parent of the target key
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                elif not isinstance(current[key], dict):
                    current[key] = {}
                current = current[key]
            
            # Set the final value
            current[keys[-1]] = value
        except (AttributeError, TypeError, IndexError):
            pass
    
    def has_required_keys(self, required_keys: List[str]) -> bool:
        """Check if all required keys exist."""
        return all(self.exists_key(key) for key in required_keys)
    
    def has_value(self, key_path: str) -> bool:
        """Check if a value exists at the given key path (not None)."""
        return self.get(key_path) is not None

    def to_dict(self) -> Dict[str, Any]:
        """Return a copy of the data as a dict."""
        return self.data.copy()


class YamlReader:
    """Static methods for reading YAML files and strings."""
    
    @staticmethod
    def read_yaml(file_path: Union[str, Path]) -> YamlFile:
        """Read a YAML file and return a YamlFile object.
        
        Raises:
            FileNotFoundError: If the file does not exist or cannot be read.
        """
        try:
            file_path = Path(file_path)
            if not file_path.exists():
                raise FileNotFoundError(f"File '{file_path}' not found")

            with open(file_path, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file) or {}
                return YamlFile(data, file_path)
        except (yaml.YAMLError, IOError, UnicodeDecodeError):
            raise FileNotFoundError(f"File '{file_path}' not found or invalid")
        
    @staticmethod
    def read_yaml_str(yaml_str: str) -> YamlFile:
        """Parse a YAML string and return a YamlFile object.
        
        Raises:
            ValueError: If the string is not valid YAML.
        """
        try:
            data = yaml.safe_load(yaml_str) or {}
            return YamlFile(data)
        except yaml.YAMLError:
            raise ValueError("Invalid YAML string:\n" + yaml_str)


__all__ = ["YamlFile", "YamlReader"]

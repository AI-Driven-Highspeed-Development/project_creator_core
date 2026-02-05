# DEPRECATED_P3: This entire module is deprecated.
# Templates are now embedded directly in project_creator.py and module_creator.py
# as Python string constants. No external template repos are used.
# This file is kept for backward compatibility but should not be used.
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Any

from .yaml_utils import YamlFile


@dataclass
class TemplateInfo:
	"""DEPRECATED_P3: Use embedded templates instead."""
	name: str
	description: str
	url: str


def list_project_templates(yf: YamlFile) -> List[TemplateInfo]:
	"""DEPRECATED_P3: Templates are now embedded in project_creator.py.
	
	This function is kept for backward compatibility only.
	
	Extract list of templates (dict-only format).

	Canonical schema:
	  <template_name>:
		description: str
		url: str
	"""
	data = yf.to_dict()
	if not isinstance(data, dict):
		raise ValueError("templates YAML must be a mapping of template name -> {description, url}")

	out: List[TemplateInfo] = []
	for name, value in data.items():
		if not isinstance(value, dict):
			raise ValueError("Each template entry must be a mapping with 'description' and 'url'")
		desc = str(value.get("description", ""))
		url = str(value.get("url", ""))
		if url:
			out.append(TemplateInfo(name=name, description=desc, url=url))
	return out


__all__ = ["TemplateInfo", "list_project_templates"]


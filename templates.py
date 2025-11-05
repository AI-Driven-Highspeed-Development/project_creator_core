from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

from cores.yaml_reading_core.yaml_file import YamlFile


@dataclass
class TemplateInfo:
	name: str
	description: str
	url: str


def list_project_templates(yf: YamlFile) -> List[TemplateInfo]:
	"""Extract list of templates (dict-only format).

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


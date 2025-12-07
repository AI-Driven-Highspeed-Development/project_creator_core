from __future__ import annotations

from dataclasses import dataclass
from typing import List, Dict, Any

from cores.yaml_reading_core.yaml_file import YamlFile


@dataclass
class PreloadSet:
	name: str
	description: str
	urls: List[str]


def parse_preload_sets(yf: YamlFile) -> Tuple[List[str], List[PreloadSet]]:
	"""Parse the module preload sets YAML into always URLs and a list of sets.

	Canonical format (dict-only) under `options` is required:

	options:
	  SetName:
		description: str
		urls: [str, ...]
	"""
	always_raw = yf.get("always", [])
	options = yf.get("options", {})

	always: List[str] = []
	options_out: List[PreloadSet] = []

	if isinstance(always_raw, list):
		always = [str(u) for u in always_raw]
	if not isinstance(options, dict):
		raise ValueError("module_preload_sets.options must be a mapping of set name -> {description, urls}")

	for name, value in options.items():
		desc = ""
		urls: List[str] = []
		if isinstance(value, dict):
			desc = str(value.get("description", ""))
			if isinstance(value.get("urls"), list):
				urls = [str(u) for u in value.get("urls", [])]
		options_out.append(PreloadSet(name=name, description=desc, urls=urls))

	return always, options_out


__all__ = ["PreloadSet", "parse_preload_sets"]


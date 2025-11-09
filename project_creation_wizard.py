from __future__ import annotations

from typing import Callable, Iterable, TypeVar

from cores.project_creator_core.project_creator import ProjectCreator, ProjectParams
from cores.project_creator_core.preload_sets import PreloadSet, parse_preload_sets
from cores.project_creator_core.templates import TemplateInfo, list_project_templates
from cores.questionary_core.questionary_core import QuestionaryCore
from cores.yaml_reading_core.yaml_file import YamlFile
from utils.logger_util.logger import Logger

T = TypeVar("T")


def run_project_creation_wizard(
    proj_tmpls: YamlFile,
    mod_preload_sets: YamlFile,
    *,
    prompter: QuestionaryCore,
    logger: Logger,
) -> None:
    """Guide the user through the interactive project scaffolding workflow."""

    try:
        project_name = prompter.autocomplete_input(
            "Project name",
            choices=[],
            default="my-project",
        )
        dest_path = prompter.path_input(
            "Destination path",
            default=f"./{project_name}",
            only_directories=False,
        )
    except KeyboardInterrupt:
        logger.info("Input cancelled. Exiting.")
        return

    templates: list[TemplateInfo] = list_project_templates(proj_tmpls)
    if not templates:
        logger.error("No project templates found in configuration.")
        return

    template_lookup = _choices_map(
        templates,
        formatter=lambda tmpl: f"{tmpl.name} — {tmpl.description or tmpl.url}",
    )
    try:
        selected_template_label = prompter.multiple_choice(
            "Select a project template",
            list(template_lookup.keys()),
            default=next(iter(template_lookup)),
        )
    except KeyboardInterrupt:
        logger.info("Template selection cancelled. Exiting.")
        return
    template_url = template_lookup[selected_template_label].url

    always_urls, sets = parse_preload_sets(mod_preload_sets)
    preload_lookup = _choices_map(
        ["None", *sets],
        formatter=lambda item: "None"
        if isinstance(item, str)
        else f"{item.name} — {item.description}",
    )
    try:
        selected_set_label = prompter.multiple_choice(
            "Select a module preload set",
            list(preload_lookup.keys()),
            default=next(iter(preload_lookup)),
        )
    except KeyboardInterrupt:
        logger.info("Preload selection cancelled. Exiting.")
        return

    selected_urls: list[str] = []
    preload_value = preload_lookup[selected_set_label]
    if isinstance(preload_value, PreloadSet):
        selected_urls = preload_value.urls

    module_urls = list(dict.fromkeys(always_urls + selected_urls))

    params = ProjectParams(
        repo_path=dest_path,
        module_urls=module_urls,
        project_name=project_name,
    )
    creator = ProjectCreator(params)
    try:
        dest = creator.create(template_url)
    except Exception as exc:  # pragma: no cover - CLI flow
        logger.error(f"❌ Failed to create project: {exc}")
        return

    logger.info(f"✅ Project created at: {dest}")


def _choices_map(items: Iterable[T], *, formatter: Callable[[T], str]) -> dict[str, T]:
    """Return an ordered mapping of menu labels to original items."""

    lookup: dict[str, T] = {}
    for item in items:
        label = formatter(item)
        if label in lookup:
            raise ValueError("Duplicate option label generated for choices")
        lookup[label] = item
    return lookup


__all__ = ["run_project_creation_wizard"]

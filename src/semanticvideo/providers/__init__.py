"""Built-in visual-description providers."""

from semanticvideo.providers.json_file import JsonFileShotDescriber
from semanticvideo.providers.openai import OpenAIShotDescriber

__all__ = ["JsonFileShotDescriber", "OpenAIShotDescriber"]

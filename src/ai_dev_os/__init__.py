"""
AI Development Operating System (ai-dev-os)

A meta-framework for orchestrating Claude Code agents across complex software projects.
Implements OMC, Ralph Loop, specum, RALPLAN, GSD, and Team Pipeline patterns.
"""

__version__ = "1.0.0"
__author__ = "krzemienski"
__license__ = "MIT"

from ai_dev_os.omc.catalog import AgentCatalog
from ai_dev_os.omc.routing import ModelRouter
from ai_dev_os.omc.state import StateManager
from ai_dev_os.ralph_loop.loop import RalphLoop
from ai_dev_os.specum.pipeline import SpecumPipeline
from ai_dev_os.ralplan.deliberate import RalplanDeliberation
from ai_dev_os.gsd.phases import GSDProject
from ai_dev_os.team_pipeline.pipeline import TeamPipeline

__all__ = [
    "__version__",
    "AgentCatalog",
    "ModelRouter",
    "StateManager",
    "RalphLoop",
    "SpecumPipeline",
    "RalplanDeliberation",
    "GSDProject",
    "TeamPipeline",
]

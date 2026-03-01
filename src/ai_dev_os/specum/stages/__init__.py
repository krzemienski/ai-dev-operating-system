"""
Specum pipeline stages.

Each stage transforms an input artifact into an output artifact
using a specialized agent persona.
"""

from ai_dev_os.specum.stages.requirements import RequirementsStage
from ai_dev_os.specum.stages.design import DesignStage
from ai_dev_os.specum.stages.tasks import TaskStage
from ai_dev_os.specum.stages.implement import ImplementStage
from ai_dev_os.specum.stages.verify import VerifyStage

__all__ = [
    "RequirementsStage",
    "DesignStage",
    "TaskStage",
    "ImplementStage",
    "VerifyStage",
]

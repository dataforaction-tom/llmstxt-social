"""Templates and examples for different organisation types."""

from .charity import CHARITY_EXAMPLE
from .funder import FUNDER_EXAMPLE
from .sectors_goals import (
    TEMPLATE_SECTORS,
    TEMPLATE_GOALS,
    DEFAULT_SECTOR,
    DEFAULT_GOALS,
    get_sectors_for_template,
    get_goals_for_template,
    get_sector_by_id,
    get_goal_by_id,
    get_default_goal,
    validate_sector,
    validate_goal,
    SectorOption,
    GoalOption,
)

__all__ = [
    "CHARITY_EXAMPLE",
    "FUNDER_EXAMPLE",
    "TEMPLATE_SECTORS",
    "TEMPLATE_GOALS",
    "DEFAULT_SECTOR",
    "DEFAULT_GOALS",
    "get_sectors_for_template",
    "get_goals_for_template",
    "get_sector_by_id",
    "get_goal_by_id",
    "get_default_goal",
    "validate_sector",
    "validate_goal",
    "SectorOption",
    "GoalOption",
]

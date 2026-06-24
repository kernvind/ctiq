
from typing import Protocol
from src.app.modules.trial_search.planning.schemas import QueryPlan


class QueryPlannerProtocol(Protocol):
    # Async: the LLM planner makes a network call. Sync planners (rule-based) are wrapped
    # via SyncPlannerAdapter so the service always awaits one uniform interface.
    async def plan(self, query: str) -> QueryPlan: ...

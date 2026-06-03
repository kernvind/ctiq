
from typing import  Protocol
from src.app.modules.trial_search.planning.schemas import QueryPlan

class QueryPlannerProtocol(Protocol):
    def plan(self, query: str) -> QueryPlan: ...

from typing import Dict, List, Optional, Tuple

from trading_core.grid.grid_models import GridSession


class GridRegistry:

    def __init__(self):
        self._sessions: Dict[Tuple[str, str], GridSession] = {}

    def save_session(self, session: GridSession) -> None:
        key = (session.symbol, session.position_side)
        self._sessions[key] = session

    def get_session(self, symbol: str, position_side: str) -> Optional[GridSession]:
        return self._sessions.get((symbol, position_side))

    def remove_session(self, symbol: str, position_side: str) -> None:
        self._sessions.pop((symbol, position_side), None)

    def get_all_sessions(self) -> List[GridSession]:
        return list(self._sessions.values())

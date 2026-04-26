from abc import ABC, abstractmethod
from typing import List
from ..models import CodeChange, ReviewFinding


class BaseChecker(ABC):
    """Base class for all code checkers."""
    
    category: str
    
    @abstractmethod
    def check(self, change: CodeChange) -> List[ReviewFinding]:
        """Check a code change and return findings."""
        pass

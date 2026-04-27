from abc import ABC, abstractmethod
from typing import List
from concurrent.futures import ThreadPoolExecutor
from ..models import CodeChange, ReviewFinding


class BaseChecker(ABC):
    """Base class for all code checkers."""

    category: str

    @abstractmethod
    def check(self, change: CodeChange) -> List[ReviewFinding]:
        """Check a code change and return findings."""
        pass

    def check_batch(self, changes: List[CodeChange]) -> List[ReviewFinding]:
        """Check multiple files in parallel."""
        with ThreadPoolExecutor(max_workers=10) as executor:
            results = list(executor.map(self.check, changes))

        # Flatten and filter None results
        all_findings = []
        for r in results:
            if r:
                all_findings.extend(r)
        return all_findings

"""Tests for code-review-agent"""

import pytest
from code_review_agent.models import CodeChange, ReviewFinding, Severity


def test_code_change_parsing():
    change = CodeChange(
        file_path="src/main.py",
        diff="""@@ -1,5 +1,7 @@
 def hello():
-    print("hello")
+    name = os.getenv("NAME")
+    if not name:
+        raise ValueError("Name is required")
+    print(f"hello {name}")
 return None
""",
        language="Python"
    )
    assert change.file_path == "src/main.py"
    assert change.language == "Python"


def test_review_finding():
    finding = ReviewFinding(
        title="Missing error handling",
        description="This function doesn't handle the case when X is None",
        severity=Severity.MAJOR,
        category="correctness"
    )
    assert finding.severity == Severity.MAJOR
    assert finding.category == "correctness"

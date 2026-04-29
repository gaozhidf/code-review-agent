"""
Golden dataset for testing code review agent.
Contains known issues that should be detected by the review process.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List


class IssueType(Enum):
    """Type of issue in the test case."""
    SQL_INJECTION = "sql_injection"
    XSS = "xss"
    HARD_CODED_SECRET = "hard_coded_secret"
    MISSING_ERROR_HANDLING = "missing_error_handling"
    RACE_CONDITION = "race_condition"
    N_PLUS_ONE = "n_plus_one"
    MEMORY_LEAK = "memory_leak"
    DEAD_CODE = "dead_code"
    COMPLEXITY = "complexity"
    MISSING_VALIDATION = "missing_validation"


@dataclass
class TestCase:
    """A test case with known issues."""
    name: str
    language: str
    file_path: str
    diff: str
    expected_issue_types: List[IssueType]
    description: str = ""


# Golden dataset
GOLDEN_DATASET: List[TestCase] = [
    TestCase(
        name="SQL Injection Vulnerability",
        language="python",
        file_path="src/api.py",
        diff="""```diff
@@ -10,7 +10,7 @@
 def get_user(user_id):
-    query = "SELECT * FROM users WHERE id = " + user_id
+    query = f"SELECT * FROM users WHERE id = {user_id}"
     cursor.execute(query)
     return cursor.fetchone()
```""",
        expected_issue_types=[IssueType.SQL_INJECTION],
        description="SQL injection via f-string interpolation",
    ),
    TestCase(
        name="XSS Vulnerability",
        language="javascript",
        file_path="src/components/UserInput.jsx",
        diff="""```diff
@@ -5,5 +5,5 @@
 function UserInput({ name }) {
   return (
-    <div>{name}</div>
+    <div dangerouslySetInnerHTML={{__html: name}} />
   );
 }
```""",
        expected_issue_types=[IssueType.XSS],
        description="XSS via dangerouslySetInnerHTML",
    ),
    TestCase(
        name="Hardcoded API Key",
        language="python",
        file_path="src/config.py",
        diff="""```diff
@@ -1,4 +1,5 @@
+API_KEY = "sk-1234567890abcdef"
+
 def get_config():
     return {"debug": True}
```""",
        expected_issue_types=[IssueType.HARD_CODED_SECRET],
        description="Hardcoded API key exposed in source",
    ),
    TestCase(
        name="Missing Error Handling",
        language="python",
        file_path="src/service.py",
        diff="""```diff
@@ -8,5 +8,5 @@
 def fetch_data(url):
-    response = requests.get(url)
+    response = requests.get(url, timeout=5)
     return response.json()
```""",
        expected_issue_types=[IssueType.MISSING_ERROR_HANDLING],
        description="Missing try-except and no timeout",
    ),
    TestCase(
        name="N+1 Query Problem",
        language="python",
        file_path="src/models.py",
        diff="""```diff
@@ -10,7 +10,7 @@
 def get_all_users_with_posts():
     users = db.query(User).all()
     for user in users:
-        posts = db.query(Post).filter_by(user_id=user.id).all()
+        posts = user.posts  # Assuming lazy loading
         process(posts)
     return users
```""",
        expected_issue_types=[IssueType.N_PLUS_ONE],
        description="N+1 query in loop",
    ),
    TestCase(
        name="Race Condition",
        language="python",
        file_path="src/counter.py",
        diff="""```diff
@@ -5,6 +5,6 @@
 class Counter:
     def increment(self):
-        self.value += 1
+        self.value = self.value + 1
     
     def get(self):
         return self.value
```""",
        expected_issue_types=[IssueType.RACE_CONDITION],
        description="Non-atomic increment operation",
    ),
    TestCase(
        name="Missing Input Validation",
        language="python",
        file_path="src/validator.py",
        diff="""```diff
@@ -8,5 +8,5 @@
 def create_user(username, email):
-    user = User(username=username, email=email)
+    user = User(username=username.strip(), email=email.lower())
     db.add(user)
     db.commit()
```""",
        expected_issue_types=[IssueType.MISSING_VALIDATION],
        description="No input sanitization before database insert",
    ),
    TestCase(
        name="Dead Code",
        language="python",
        file_path="src/utils.py",
        diff="""```diff
@@ -15,5 +15,5 @@
 # This function is never called
 def unused_function():
-    return process_data(data)
+    pass
     
 def main():
```""",
        expected_issue_types=[IssueType.DEAD_CODE],
        description="Function returns value but is never used",
    ),
]


def get_test_case(name: str) -> TestCase:
    """Get a test case by name."""
    for case in GOLDEN_DATASET:
        if case.name == name:
            return case
    raise ValueError(f"Test case '{name}' not found")


def get_test_cases_by_issue_type(issue_type: IssueType) -> List[TestCase]:
    """Get all test cases for a specific issue type."""
    return [case for case in GOLDEN_DATASET if issue_type in case.expected_issue_types]

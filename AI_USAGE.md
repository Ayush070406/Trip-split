# AI_USAGE.md - AI Collaboration Log

This document records the AI tools, key prompts, and instances of error correction during the development of the Shared Expenses application.

---

## 1. AI Tools Used
- **Primary Collaborator**: Antigravity AI Agent (powered by Google DeepMind team, running Gemini 3.5 Flash).
- **IDE & Shell**: PowerShell Terminal Integration on Windows 11.

---

## 2. Key Prompts

1. **Initial Project Analysis**:
   > "I will list the contents of the Desktop to find expenses_export.csv and see what files exist in the project workspace."
2. **Framework Modification**:
   > "we have to create backend with flask and frontend with react. the database will be postgresql"
3. **Execution Commands**:
   > "I will run python using its absolute path to verify that it functions correctly and check its version."

---

## 3. Concrete Errors and Corrections

### Case 1: NPM Package Naming Space Violation
- **AI Action**: The agent attempted to initialize Next.js in the root directory using:
  `npx create-next-app@14 ./ --js --eslint --app`
- **How it failed**: The project folder name `new project company` contains spaces. NPM naming restrictions forbid package names containing spaces, causing `create-next-app` to crash with:
  `Could not create a project called "new project company" because of npm naming restrictions.`
- **How we caught it**: The terminal command returned an exit code of `1`.
- **How we resolved it**: We initialized the project inside a subdirectory named `shared-expenses-app` (valid URL-friendly string), and then wrote a PowerShell script to move all files (including hidden `.git` and `.gitignore`) up to the root directory and delete the subdirectory.

### Case 2: Python Relative Module Import Failure
- **AI Action**: The agent attempted to run a test module inside the `backend/` folder:
  `.\venv\Scripts\python -c "import app"`
- **How it failed**: The script threw a `ModuleNotFoundError: No module named 'backend'` at line `from backend.database import db`. This happened because the script was executed inside the `backend` folder, but the code files write imports referencing `backend.database` which expects the parent workspace root to be in the python path.
- **How we caught it**: The test command crashed with a Python traceback.
- **How we resolved it**: We ran the python runner from the workspace root directory:
  `& backend\venv\Scripts\python -c "import backend.app"`
  This correctly added the workspace root to Python’s path, allowing the packages to resolve.

### Case 3: Failed CSV Duplicate and Conflict Detection
- **AI Action**: The agent wrote a simple description similarity check inside `backend/importer.py` using:
  `desc_sim = (r1['description'].lower() in r2['description'].lower() or ...)`
- **How it failed**: It failed to detect the Marina Bites duplicate entries (Row 5 `Dinner at Marina Bites` vs Row 6 `dinner - marina bites`) and the Thalassa conflict entries (Row 24 `Dinner at Thalassa` vs Row 25 `Thalassa dinner`) because of minor variations in prepositions and punctuation (`at` vs `-`).
- **How we caught it**: We wrote a scratch test runner `scratch_test_import.py` to print all detected anomalies, and noticed that duplicates and conflicts were missing from the list.
- **How we resolved it**: We wrote a custom helper function `is_desc_similar(d1, d2)` which cleans descriptions, strips punctuation, removes common prepositions/words (stop words like `at`, `for`, `dinner`, `lunch`, `order`, `-`), and checks if the intersection of their word sets is non-empty. This resolved the issue, and successfully flagged the duplicates and conflicts.

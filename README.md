# Shared Expenses App (Trip Split)

A shared expenses application built to parse, detect, resolve, and manage shared expenses for Aisha, Rohan, Priya, Meera, Sam, and Dev. It includes a multi-step CSV importer that detects 24 data anomalies and provides interactive resolution UI.

---

## 🚀 Tech Stack

- **Frontend**: React (Vite, JavaScript) styled with custom premium Vanilla CSS (Glassmorphism, Dark Mode, responsive layouts).
- **Backend**: Flask (Python 3.12) with JWT cookie-based authentication.
- **ORM & Database**: SQLAlchemy ORM connecting to **PostgreSQL** in production, with an out-of-the-box local SQLite fallback for developer convenience.
- **AI Collaboration**: Built in partnership with Antigravity AI Agent (DeepMind team).

---

## 🛠️ Local Setup Instructions

### Prerequisites
- **Node.js** (v18+) and **npm**
- **Python** (v3.12+)

---

### 1. Backend Setup

1. Open a terminal in the root directory.
2. Create and activate a virtual environment:
   ```powershell
   cd backend
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```
3. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```
4. Configure environment variables in `.env` (optional). If not configured, the app will automatically default to SQLite (`sqlite:///expenses.db`) in the root:
   ```env
   JWT_SECRET=your_jwt_secret
   DATABASE_URL=postgresql://user:password@localhost:5432/dbname
   ```
5. Run the Flask server:
   ```powershell
   # Run from root project directory for relative paths
   cd ..
   & backend\venv\Scripts\python backend\app.py
   ```
   *The server runs on `http://localhost:5000`.*

---

### 2. Frontend Setup

1. Open a new terminal in the `frontend` folder:
   ```powershell
   cd frontend
   ```
2. Install npm packages:
   ```powershell
   npm install
   ```
3. Run the Vite React development server:
   ```powershell
   npm run dev
   ```
   *The client runs on `http://localhost:5173`.*

---

## 🧪 Running Unit Tests

To run the Python unit tests verifying date parsing, cleaning, mapping, and debt minimization:
```powershell
cd backend
.\venv\Scripts\python tests.py
```

---

## 📥 Import Wizard and Resolution Flow

1. Register an account and login.
2. Select or create an expense group.
3. Click on the **CSV Data Importer** tab.
4. Drag and drop `expenses_export.csv` into the box, then click **Upload and Check**.
5. The importer will show all 24 anomalies. Configure the resolution choices (e.g., select which Thalassa dinner or Marina Bites duplicates to keep, enter FX rates for USD items, map spelling aliases).
6. Click **Save Resolutions**.
7. The app displays the **Final Import Report** showing what was imported and skipped. You can download this report as a text file.

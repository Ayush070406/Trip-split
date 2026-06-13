# DECISIONS.md - Decisions Log

This document records the design and architectural decisions made while building the Shared Expenses App, detailing the alternatives considered and the reasons behind our selections.

---

## 1. Backend Framework: Flask (Python)
- **Option A (Considered)**: Next.js API Routes (Serverless/Node.js).
- **Option B (Selected)**: Flask (Python).
- **Rationale**: The user explicitly requested a Flask backend. Flask is lightweight, highly customizable, and excels at writing custom API endpoints. Python’s powerful string processing and built-in CSV parser make implementing anomaly detection extremely straightforward and readable.

## 2. Frontend Framework: React (Vite)
- **Option A (Considered)**: Next.js App Router.
- **Option B (Selected)**: Vite + React.
- **Rationale**: Vite provides a modern, blazing-fast bundling experience for Single Page Applications (SPAs) without the server-side rendering complexity of Next.js. Combining React (Vite) with a Flask backend creates a clean decoupling of the client and server layers.

## 3. Database: PostgreSQL (with SQLite Local Fallback)
- **Option A (Considered)**: Prisma ORM with SQLite only.
- **Option B (Selected)**: PostgreSQL with SQLAlchemy ORM (and SQLite local fallback).
- **Rationale**: PostgreSQL is a robust relational database. We utilize SQLAlchemy in Flask to represent models. To ensure the app can be run locally *out-of-the-box* without requiring the user to install a local PostgreSQL server, the app defaults to a local SQLite database (`sqlite:///expenses.db`) if no `DATABASE_URL` is set in the environment. Because SQLAlchemy abstracts SQL dialects, the exact same code runs seamlessly on SQLite locally and on PostgreSQL when deployed, satisfying both usability and technical requirements.

## 4. Date-Based Memberships (Sam's Request)
- **Problem**: Sam moved in mid-April and does not want March electricity bills affecting his balance. Meera moved out in March and should not split April expenses.
- **Option A (Considered)**: Group membership is static, and users are manually unticked from splits.
- **Option B (Selected)**: Date-based group membership. Every `GroupMember` record contains `joined_at` and `left_at` fields.
- **Rationale**: When an expense is recorded (or imported), the app automatically validates the expense date against each member's active membership range. If they were inactive on that date, they are excluded from the split. This ensures March rent/electricity automatically excludes Sam, while April rent/groceries automatically excludes Meera, solving the problem systematically without manual tracking.

## 5. CSV Anomaly Resolution Flow (Meera's Request)
- **Problem**: The CSV file contains multiple data problems. Meera requests that duplicates and changes be approved before deletion or ingestion.
- **Option A (Considered)**: Silent guessing (making the app guess the resolution during import) or rejecting the file.
- **Option B (Selected)**: Draft Ingestion & Interactive Anomaly Dashboard.
- **Rationale**: Ingesting the messy CSV file creates a temporary "pending" session and saves all detected anomalies in the database. The React frontend reads these anomalies and presents them to the user in a wizard. The user can review the proposed changes (e.g. mapping names, merging duplicates, resolving conflicts, setting USD FX rates, and normalizing percentages) and click "Confirm". Only upon confirmation are the clean records created in the primary tables. This guarantees Meera can explicitly approve every database write.

## 6. Debt Simplification (Aisha's Request)
- **Problem**: Aisha wants a single number per person ("Who pays whom, how much, done").
- **Option A (Considered)**: Pairwise debts (A owes B, B owes C, etc.), leading to a web of many payments.
- **Option B (Selected)**: Greedy Cash Flow Minimization Algorithm (Splitwise-style).
- **Rationale**: By summing all expenses paid, splits owed, and settlements sent/received, we calculate a single net balance for each member. We then pair the largest debtor with the largest creditor. This minimizes the total number of transactions to the mathematical minimum ($N-1$ transactions maximum, where $N$ is the number of members), providing the simplified "one number per person" Aisha requested.

## 7. No Magic Numbers (Rohan's Request)
- **Problem**: Rohan wants to verify how his balance is calculated.
- **Option A (Selected)**: Interactive Ledger.
- **Rationale**: Clicking on any user card shows their detailed ledger, which lists every single transaction where they paid or owed. USD conversions and split percentages are printed explicitly in the line item descriptions. This provides total transparency and eliminates "magic numbers."

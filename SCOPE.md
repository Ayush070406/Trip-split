# SCOPE.md - Anomaly Log & Database Schema

This document details the anomalies identified in `expenses_export.csv` and outlines the relational database schema of the Shared Expenses application.

---

## 1. CSV Anomaly Log (24 Detected Issues)

Our custom importer parses the spreadsheet row-by-row and detects 24 deliberate data problems. We present these anomalies to the user in the **Import Resolution Wizard** before committing the data.

| Row | Anomaly Type | Description of Messy Data | Resolution Policy & Action |
| --- | --- | --- | --- |
| **5 & 6** | `duplicate` | Identical date, paid_by (`Dev`), amount (`3200`), and splits logged twice: "Dinner at Marina Bites" vs "dinner - marina bites". | **User Decision**: Show side-by-side. The default policy ignores Row 6 (duplicate) and imports only Row 5. |
| **7** | `quoted_amount` | Amount is formatted inside quotes with a thousands comma separator: `"1,200"`. | **Automated Clean**: Strip quotes and commas, parse as `1200.0`. |
| **9** | `name_alias` | Payer `priya` is in lowercase, which differs from core capitalization. | **Name Mapping**: Normalizes case-insensitively and maps to `Priya`. |
| **10** | `high_precision_amount` | Cylinder refill amount has 3 decimal places: `899.995`. | **Automated Round**: Round to 2 decimal places (`900.00`) and record. |
| **11** | `name_alias` | Payer is recorded as `Priya S` instead of the member name `Priya`. | **Name Mapping**: Maps variant/spelling `Priya S` to the registered user `Priya`. |
| **13** | `missing_payer` | Payer field is left completely blank ("can't remember who paid"). | **User Required input**: Show dropdown to select the actual payer before saving. |
| **14** | `settlement_disguised` | Settlement payment ("Rohan paid Aisha back", `5000`) is logged as a split expense. | **Convert Type**: Do not split. Record as a direct `Settlement` from Rohan to Aisha. |
| **15** | `invalid_percentage_sum` | Pizza Friday split percentages (30%, 30%, 30%, 20%) sum up to 110%. | **Proportional Scale**: Normalize splits by dividing by 1.1 so they sum to 100%. |
| **20** | `usd_transaction` | Villa booking amount is logged in US Dollars (`540` USD). | **FX Conversion**: Require an FX exchange rate (defaulting to 83.0 INR/USD) and store both original USD and converted INR. |
| **21** | `usd_transaction` | Beach shack lunch is in USD (`84` USD). | **FX Conversion**: Convert to INR (84 * 83 = 6,972 INR). |
| **23** | `usd_transaction` | Parasailing is in USD (`150` USD). | **FX Conversion**: Convert to INR (150 * 83 = 12,450 INR). |
| **23** | `guest_split` | Split list includes `Dev's friend Kabir` who is an external guest. | **User Decision**: Either assign Kabir's share to Dev (Dev pays for guest) or add Kabir as a member. |
| **24 & 25** | `conflict` | Same event (Thalassa Dinner on 11-03-2026) logged twice but with different payers and amounts (Aisha ₹2400 vs Rohan ₹2450). | **User Decision**: Show conflict. Select which row is correct. Rohan's note says "Aisha's is wrong," so keep Row 25 and ignore Row 24. |
| **26** | `negative_amount` | Parasailing refund is logged as negative amount (`-30` USD). | **Refund Logic**: Keep negative amount to reduce Dev's total payment and reduce others' owed splits. |
| **26** | `usd_transaction` | Refund is in USD (`-30` USD). | **FX Conversion**: Convert to INR (-30 * 83 = -2,490 INR). |
| **27** | `inconsistent_date_format`| Date is formatted as text `Mar-14` instead of standard `DD-MM-YYYY`. | **Date Correction**: Parse month and day and insert as `14-03-2026`. |
| **27** | `name_casing` | Payer is logged with trailing whitespace and lowercase: `rohan `. | **Clean & Normalize**: Trim whitespace, case-insensitively map to `Rohan`. |
| **28** | `missing_currency` | Currency is blank for groceries. Note: "forgot to set currency". | **Default Policy**: Auto-fill with the default group currency `INR`. |
| **31** | `zero_amount` | Amount is `0`. Note: "counted twice earlier - fixing later". | **Skip Row**: Suggest skipping this row to prevent database noise. |
| **32** | `invalid_percentage_sum` | Weekend brunch percentages sum to 110% (30% * 3 + 20%). | **Proportional Scale**: Normalize to 100%. |
| **34** | `ambiguous_date` | Date is `04-05-2026` but note and sequence suggest April 5. | **Date Choice**: Prompt user to use `05-04-2026` based on chronological sequence. |
| **36** | `inactive_member_split` | Split includes Meera on April 2, but Meera moved out in March. | **Membership Check**: Exclude Meera. Recalculate split among active members (Aisha, Rohan, Priya). |
| **38** | `settlement_disguised` | "Sam deposit share" (`15000`) is logged as an expense. | **Convert Type**: Record as a direct `Settlement` from Sam to Aisha. |
| **42** | `redundant_split_details` | Split type is `equal` but shares `Aisha 1; Rohan 1; Priya 1; Sam 1` are provided anyway. | **Disregard**: Ignore the redundant details and split equally. |

---

## 2. Database Schema

The database is built on **PostgreSQL** (with local fallback to SQLite) and managed via **SQLAlchemy ORM**. It is fully relational, using foreign keys, cascade deletes, and unique constraints.

```mermaid
erDiagram
    users {
        string id PK
        string username UNIQUE
        string password_hash
        string name
        datetime created_at
    }
    groups {
        string id PK
        string name
        datetime created_at
    }
    group_members {
        string id PK
        string group_id FK
        string user_id FK
        datetime joined_at
        datetime left_at
    }
    expenses {
        string id PK
        string group_id FK
        string description
        float amount
        string currency
        float exchange_rate
        float amount_in_inr
        string paid_by_id FK
        string split_type
        datetime date
        text notes
        boolean is_settlement
        datetime created_at
    }
    expense_splits {
        string id PK
        string expense_id FK
        string user_id FK
        float amount_in_inr
        float split_value
    }
    settlements {
        string id PK
        string group_id FK
        string payer_id FK
        string payee_id FK
        float amount_in_inr
        datetime date
        text notes
        datetime created_at
    }
    import_sessions {
        string id PK
        string status
        string file_name
        datetime created_at
    }
    import_anomalies {
        string id PK
        string import_session_id FK
        int row_index
        text raw_row
        string anomaly_type
        text description
        string suggested_action
        string user_action
        string status
    }

    users ||--o{ group_members : has
    groups ||--o{ group_members : contains
    groups ||--o{ expenses : contains
    groups ||--o{ settlements : contains
    users ||--o{ expenses : pays
    expenses ||--o{ expense_splits : splits
    users ||--o{ expense_splits : owes
    users ||--o{ settlements : sends
    users ||--o{ settlements : receives
    import_sessions ||--o{ import_anomalies : has
```

### Table Definitions & Key Relationships

1. **`users`**:
   - Stores user credentials. `password_hash` is computed using Bcrypt.
   - Core members (Aisha, Rohan, Priya, Meera, Sam, Dev) are populated in this table.
2. **`groups`**:
   - Holds shared expense groups.
3. **`group_members`**:
   - Maps users to groups. Supports **date-based membership** (`joined_at` and `left_at`).
   - A unique constraint `(group_id, user_id)` prevents duplicate memberships.
4. **`expenses`**:
   - Records each expense transaction, noting the original currency/amount and the computed `amount_in_inr` using the applied `exchange_rate`.
5. **`expense_splits`**:
   - Relational splits mapping portions of an expense to members. `amount_in_inr` stores the exact liability.
6. **`settlements`**:
   - Records direct peer-to-peer debt payments. Reduces net balance directly.
7. **`import_sessions` & `import_anomalies`**:
   - Tracks uploaded CSV imports and stores pending anomaly resolutions so the import state is fully auditable.

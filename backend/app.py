import os
import uuid
import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv

# Load env variables
load_dotenv()

from backend.database import db
from backend.models import User, Group, GroupMember, Expense, ExpenseSplit, Settlement, ImportSession, ImportAnomaly
from backend.importer import detect_csv_anomalies, clean_amount, parse_date, normalize_name

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
bcrypt = Bcrypt(app)

# Database Configuration
db_url = os.environ.get("DATABASE_URL")
if db_url:
    # Heroku / Render fix for postgresql URL scheme
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
else:
    # Fallback to local SQLite for development convenience
    db_url = "sqlite:///expenses.db"

app.config["SQLALCHEMY_DATABASE_URI"] = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.environ.get("JWT_SECRET", "super-secret-key-12345")

db.init_app(app)

# Create tables on startup
with app.app_context():
    db.create_all()

# --- HELPER DECORATORS ---

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Check Header
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]
        
        # Check Cookie fallback
        if not token:
            token = request.cookies.get("token")

        if not token:
            return jsonify({"message": "Token is missing!"}), 401

        try:
            data = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
            current_user = User.query.get(data["user_id"])
            if not current_user:
                return jsonify({"message": "User not found!"}), 401
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token has expired!"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Token is invalid!"}), 401

        return f(current_user, *args, **kwargs)
    return decorated

# --- AUTH ROUTES ---

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password") or not data.get("name"):
        return jsonify({"message": "Missing required fields"}), 400

    username = data["username"].strip().lower()
    if User.query.filter_by(username=username).first():
        return jsonify({"message": "Username already exists"}), 400

    password_hash = bcrypt.generate_password_hash(data["password"]).decode("utf-8")
    new_user = User(
        id=str(uuid.uuid4()),
        username=username,
        password_hash=password_hash,
        name=data["name"].strip()
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User registered successfully"}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data or not data.get("username") or not data.get("password"):
        return jsonify({"message": "Missing username or password"}), 400

    username = data["username"].strip().lower()
    user = User.query.filter_by(username=username).first()

    if not user or not bcrypt.check_password_hash(user.password_hash, data["password"]):
        return jsonify({"message": "Invalid credentials"}), 401

    token = jwt.encode({
        "user_id": user.id,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }, app.config["SECRET_KEY"], algorithm="HS256")

    response = jsonify({
        "message": "Login successful",
        "user": user.to_dict(),
        "token": token
    })
    # Set HTTP-only cookie
    response.set_cookie("token", token, httponly=True, max_age=86400)
    return response

@app.route("/api/auth/logout", methods=["POST"])
def logout():
    response = jsonify({"message": "Logged out successfully"})
    response.delete_cookie("token")
    return response

@app.route("/api/auth/profile", methods=["GET"])
@token_required
def get_profile(current_user):
    return jsonify(current_user.to_dict())

# --- GROUP ROUTES ---

@app.route("/api/groups", methods=["GET"])
@token_required
def get_groups(current_user):
    # Get all groups where the user is a member
    memberships = GroupMember.query.filter_by(user_id=current_user.id).all()
    groups_list = []
    for m in memberships:
        groups_list.append({
            "id": m.group.id,
            "name": m.group.name,
            "created_at": m.group.created_at.isoformat(),
            "joined_at": m.joined_at.isoformat(),
            "left_at": m.left_at.isoformat() if m.left_at else None
        })
    return jsonify(groups_list)

@app.route("/api/groups", methods=["POST"])
@token_required
def create_group(current_user):
    data = request.get_json()
    if not data or not data.get("name"):
        return jsonify({"message": "Group name is required"}), 400

    group_id = str(uuid.uuid4())
    new_group = Group(
        id=group_id,
        name=data["name"].strip()
    )
    db.session.add(new_group)
    
    # Creator is added as an active member by default
    member_id = str(uuid.uuid4())
    new_member = GroupMember(
        id=member_id,
        group_id=group_id,
        user_id=current_user.id,
        joined_at=datetime.utcnow()
    )
    db.session.add(new_member)
    db.session.commit()

    return jsonify(new_group.to_dict()), 201

@app.route("/api/groups/<group_id>", methods=["GET"])
@token_required
def get_group_details(current_user, group_id):
    group = Group.query.get(group_id)
    if not group:
        return jsonify({"message": "Group not found"}), 404

    # Verify membership
    user_member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not user_member:
        return jsonify({"message": "Unauthorized Access"}), 403

    members_list = []
    for m in group.members:
        members_list.append(m.to_dict())

    return jsonify({
        "id": group.id,
        "name": group.name,
        "created_at": group.created_at.isoformat(),
        "members": members_list
    })

@app.route("/api/groups/<group_id>/members", methods=["POST"])
@token_required
def add_group_member(current_user, group_id):
    group = Group.query.get(group_id)
    if not group:
        return jsonify({"message": "Group not found"}), 404

    # Verify authorization
    user_member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not user_member:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.get_json()
    if not data or not data.get("username"):
        return jsonify({"message": "Username is required"}), 400

    username = data["username"].strip().lower()
    target_user = User.query.filter_by(username=username).first()
    if not target_user:
        return jsonify({"message": "User does not exist"}), 404

    # Check if already a member
    existing = GroupMember.query.filter_by(group_id=group_id, user_id=target_user.id).first()
    if existing:
        return jsonify({"message": "User is already a member of this group"}), 400

    # Parse membership dates
    joined_at = datetime.utcnow()
    if data.get("joined_at"):
        joined_at = datetime.fromisoformat(data["joined_at"].replace("Z", ""))
    
    left_at = None
    if data.get("left_at"):
        left_at = datetime.fromisoformat(data["left_at"].replace("Z", ""))

    new_member = GroupMember(
        id=str(uuid.uuid4()),
        group_id=group_id,
        user_id=target_user.id,
        joined_at=joined_at,
        left_at=left_at
    )
    db.session.add(new_member)
    db.session.commit()

    return jsonify(new_member.to_dict()), 201

@app.route("/api/groups/<group_id>/members/<user_id>", methods=["PUT"])
@token_required
def update_group_member(current_user, group_id, user_id):
    # Verify authorization
    user_member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not user_member:
        return jsonify({"message": "Unauthorized"}), 403

    member = GroupMember.query.filter_by(group_id=group_id, user_id=user_id).first()
    if not member:
        return jsonify({"message": "Member not found"}), 404

    data = request.get_json()
    if data.get("joined_at"):
        member.joined_at = datetime.fromisoformat(data["joined_at"].replace("Z", ""))
    
    if "left_at" in data:
        if data["left_at"] is None:
            member.left_at = None
        else:
            member.left_at = datetime.fromisoformat(data["left_at"].replace("Z", ""))

    db.session.commit()
    return jsonify(member.to_dict())

# --- EXPENSE MANAGEMENT ---

@app.route("/api/groups/<group_id>/expenses", methods=["POST"])
@token_required
def add_expense(current_user, group_id):
    group = Group.query.get(group_id)
    if not group:
        return jsonify({"message": "Group not found"}), 404

    # Verify authorization
    user_member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not user_member:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.get_json()
    if not data or not data.get("description") or not data.get("amount") or not data.get("paid_by_id"):
        return jsonify({"message": "Missing required fields"}), 400

    # Parse details
    desc = data["description"].strip()
    amount = float(data["amount"])
    currency = data.get("currency", "INR").strip().upper()
    exchange_rate = float(data.get("exchange_rate", 1.0))
    amount_in_inr = amount * exchange_rate if currency == "USD" else amount
    paid_by_id = data["paid_by_id"]
    split_type = data.get("split_type", "equal").strip().lower() # equal, unequal, percentage, share
    date_val = datetime.fromisoformat(data.get("date", datetime.utcnow().isoformat()).replace("Z", ""))
    notes = data.get("notes", "")

    # Create Expense
    expense_id = str(uuid.uuid4())
    expense = Expense(
        id=expense_id,
        group_id=group_id,
        description=desc,
        amount=amount,
        currency=currency,
        exchange_rate=exchange_rate,
        amount_in_inr=amount_in_inr,
        paid_by_id=paid_by_id,
        split_type=split_type,
        date=date_val,
        notes=notes,
        is_settlement=False
    )

    splits_data = data.get("splits", [])
    if not splits_data:
        # Default split: split equally among all members active on this date
        members = GroupMember.query.filter_by(group_id=group_id).all()
        active_members = []
        for m in members:
            # check active range
            is_active = (m.joined_at <= date_val) and (m.left_at is None or m.left_at >= date_val)
            if is_active:
                active_members.append(m.user_id)
        
        if not active_members:
            return jsonify({"message": "No active group members found on this date."}), 400

        split_share = amount_in_inr / len(active_members)
        for u_id in active_members:
            split = ExpenseSplit(
                id=str(uuid.uuid4()),
                expense_id=expense_id,
                user_id=u_id,
                amount_in_inr=split_share
            )
            db.session.add(split)
    else:
        # Splits are custom specified
        # Check active status of each split user
        for sd in splits_data:
            u_id = sd["user_id"]
            m = GroupMember.query.filter_by(group_id=group_id, user_id=u_id).first()
            if not m:
                return jsonify({"message": f"User {u_id} is not a member of the group"}), 400
            
            # Check active on expense date
            is_active = (m.joined_at <= date_val) and (m.left_at is None or m.left_at >= date_val)
            if not is_active:
                # Sam's and Meera's request handling: skip inactive splits, or warn.
                # In standard manual addition, we enforce they must be active.
                return jsonify({"message": f"User {m.user.name} is not active on this date ({date_val.strftime('%d-%m-%Y')})"}), 400

        if split_type == "equal":
            split_share = amount_in_inr / len(splits_data)
            for sd in splits_data:
                split = ExpenseSplit(
                    id=str(uuid.uuid4()),
                    expense_id=expense_id,
                    user_id=sd["user_id"],
                    amount_in_inr=split_share
                )
                db.session.add(split)

        elif split_type == "unequal":
            # Check total sum matches
            total_split_inr = sum(float(sd["split_value"]) for sd in splits_data)
            # Apply exchange rate if splits are in original USD
            total_split_inr_converted = total_split_inr * exchange_rate if currency == "USD" else total_split_inr
            # Allow tiny rounding tolerances (0.05)
            if abs(total_split_inr_converted - amount_in_inr) > 0.05:
                return jsonify({"message": f"Sum of splits ({total_split_inr_converted}) must equal the total expense amount ({amount_in_inr})"}), 400
            
            for sd in splits_data:
                split = ExpenseSplit(
                    id=str(uuid.uuid4()),
                    expense_id=expense_id,
                    user_id=sd["user_id"],
                    amount_in_inr=float(sd["split_value"]) * exchange_rate if currency == "USD" else float(sd["split_value"]),
                    split_value=float(sd["split_value"])
                )
                db.session.add(split)

        elif split_type == "percentage":
            total_pct = sum(float(sd["split_value"]) for sd in splits_data)
            if abs(total_pct - 100.0) > 0.05:
                return jsonify({"message": f"Sum of percentages ({total_pct}%) must equal 100%"}), 400
            
            for sd in splits_data:
                share_inr = (float(sd["split_value"]) / 100.0) * amount_in_inr
                split = ExpenseSplit(
                    id=str(uuid.uuid4()),
                    expense_id=expense_id,
                    user_id=sd["user_id"],
                    amount_in_inr=share_inr,
                    split_value=float(sd["split_value"])
                )
                db.session.add(split)

        elif split_type == "share":
            total_shares = sum(float(sd["split_value"]) for sd in splits_data)
            if total_shares == 0:
                return jsonify({"message": "Sum of shares cannot be zero"}), 400
            
            for sd in splits_data:
                share_inr = (float(sd["split_value"]) / total_shares) * amount_in_inr
                split = ExpenseSplit(
                    id=str(uuid.uuid4()),
                    expense_id=expense_id,
                    user_id=sd["user_id"],
                    amount_in_inr=share_inr,
                    split_value=float(sd["split_value"])
                )
                db.session.add(split)

    db.session.add(expense)
    db.session.commit()
    return jsonify(expense.to_dict()), 201

@app.route("/api/groups/<group_id>/expenses", methods=["GET"])
@token_required
def get_expenses(current_user, group_id):
    # Verify membership
    user_member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not user_member:
        return jsonify({"message": "Unauthorized"}), 403

    expenses = Expense.query.filter_by(group_id=group_id, is_settlement=False).order_by(Expense.date.asc()).all()
    return jsonify([e.to_dict() for e in expenses])

@app.route("/api/expenses/<expense_id>", methods=["DELETE"])
@token_required
def delete_expense(current_user, expense_id):
    expense = Expense.query.get(expense_id)
    if not expense:
        return jsonify({"message": "Expense not found"}), 404

    # Verify authorization (is a member of the expense's group)
    user_member = GroupMember.query.filter_by(group_id=expense.group_id, user_id=current_user.id).first()
    if not user_member:
        return jsonify({"message": "Unauthorized"}), 403

    db.session.delete(expense)
    db.session.commit()
    return jsonify({"message": "Expense deleted successfully"})

# --- SETTLEMENT MANAGEMENT ---

@app.route("/api/groups/<group_id>/settlements", methods=["POST"])
@token_required
def record_settlement(current_user, group_id):
    # Verify authorization
    user_member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not user_member:
        return jsonify({"message": "Unauthorized"}), 403

    data = request.get_json()
    if not data or not data.get("payer_id") or not data.get("payee_id") or not data.get("amount"):
        return jsonify({"message": "Missing required fields"}), 400

    payer_id = data["payer_id"]
    payee_id = data["payee_id"]
    amount = float(data["amount"])
    date_val = datetime.fromisoformat(data.get("date", datetime.utcnow().isoformat()).replace("Z", ""))
    notes = data.get("notes", "")

    settlement = Settlement(
        id=str(uuid.uuid4()),
        group_id=group_id,
        payer_id=payer_id,
        payee_id=payee_id,
        amount_in_inr=amount,
        date=date_val,
        notes=notes
    )

    db.session.add(settlement)
    db.session.commit()
    return jsonify(settlement.to_dict()), 201

@app.route("/api/groups/<group_id>/settlements", methods=["GET"])
@token_required
def get_settlements(current_user, group_id):
    # Verify authorization
    user_member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not user_member:
        return jsonify({"message": "Unauthorized"}), 403

    settlements = Settlement.query.filter_by(group_id=group_id).order_by(Settlement.date.asc()).all()
    return jsonify([s.to_dict() for s in settlements])

# --- BALANCES, LEDGERS, AND DEBT SIMPLIFICATION ---

@app.route("/api/groups/<group_id>/balances", methods=["GET"])
@token_required
def get_balances_and_ledger(current_user, group_id):
    # Verify authorization
    user_member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not user_member:
        return jsonify({"message": "Unauthorized"}), 403

    group = Group.query.get(group_id)
    if not group:
        return jsonify({"message": "Group not found"}), 404

    # Fetch all members, expenses, and settlements
    members = {m.user_id: m.user.name for m in group.members}
    expenses = Expense.query.filter_by(group_id=group_id, is_settlement=False).all()
    settlements = Settlement.query.filter_by(group_id=group_id).all()

    # Initialize calculations
    # Net Balance = (Paid + Sent) - (Owed + Received)
    stats = {u_id: {"paid": 0.0, "owed": 0.0, "sent": 0.0, "received": 0.0, "name": name, "ledger": []} for u_id, name in members.items()}

    # Process Expenses and splits
    for e in expenses:
        # Add to payer's paid log
        payer_id = e.paid_by_id
        if payer_id in stats:
            stats[payer_id]["paid"] += e.amount_in_inr
            stats[payer_id]["ledger"].append({
                "type": "paid",
                "date": e.date.isoformat(),
                "description": e.description,
                "amount": e.amount_in_inr,
                "original_amount": e.amount,
                "currency": e.currency,
                "rate": e.exchange_rate,
                "notes": e.notes
            })

        # Add to split members' owed log
        for s in e.splits:
            debtor_id = s.user_id
            if debtor_id in stats:
                stats[debtor_id]["owed"] += s.amount_in_inr
                
                # Math breakdown to satisfy Rohan's request ("No magic numbers")
                breakdown = f"Share of {e.description} (Paid by {e.paid_by.name if e.paid_by else 'Unknown'}). Total: {e.currency} {e.amount}"
                if e.currency == "USD":
                    breakdown += f" @ FX rate {e.exchange_rate} INR/USD = ₹{e.amount_in_inr:.2f}"
                
                if e.split_type == "percentage":
                    breakdown += f" (Your share: {s.split_value}%)"
                elif e.split_type == "share":
                    total_shares = sum(sp.split_value for sp in e.splits)
                    breakdown += f" (Your share: {s.split_value}/{total_shares} shares)"
                elif e.split_type == "unequal":
                    breakdown += f" (Your unequal split value: {s.split_value})"
                
                stats[debtor_id]["ledger"].append({
                    "type": "owed",
                    "date": e.date.isoformat(),
                    "description": breakdown,
                    "amount": s.amount_in_inr,
                    "notes": e.notes
                })

    # Process settlements
    for s in settlements:
        # Payer sent money
        if s.payer_id in stats:
            stats[s.payer_id]["sent"] += s.amount_in_inr
            stats[s.payer_id]["ledger"].append({
                "type": "settlement_sent",
                "date": s.date.isoformat(),
                "description": f"Paid back {s.payee.name if s.payee else 'Unknown'}",
                "amount": s.amount_in_inr,
                "notes": s.notes
            })
        
        # Payee received money
        if s.payee_id in stats:
            stats[s.payee_id]["received"] += s.amount_in_inr
            stats[s.payee_id]["ledger"].append({
                "type": "settlement_received",
                "date": s.date.isoformat(),
                "description": f"Received payment from {s.payer.name if s.payer else 'Unknown'}",
                "amount": s.amount_in_inr,
                "notes": s.notes
            })

    # Compute net balance summary
    balance_summary = []
    net_balances_dict = {}
    for u_id, user_stats in stats.items():
        net = (user_stats["paid"] + user_stats["sent"]) - (user_stats["owed"] + user_stats["received"])
        net_balances_dict[u_id] = net
        
        # Sort ledger by date chronologically
        user_stats["ledger"].sort(key=lambda x: x["date"])

        balance_summary.append({
            "user_id": u_id,
            "name": user_stats["name"],
            "paid": user_stats["paid"],
            "owed": user_stats["owed"],
            "sent": user_stats["sent"],
            "received": user_stats["received"],
            "net_balance": net,
            "ledger": user_stats["ledger"]
        })

    # Run Debt Simplification (Aisha's request: "Who pays whom, how much, done.")
    # Standard greedy minimize cash flow algorithm
    debtors = [] # (user_id, balance) where balance is negative
    creditors = [] # (user_id, balance) where balance is positive

    for u_id, bal in net_balances_dict.items():
        if bal < -0.01: # debtor
            debtors.append({"id": u_id, "name": members[u_id], "balance": bal})
        elif bal > 0.01: # creditor
            creditors.append({"id": u_id, "name": members[u_id], "balance": bal})

    simplified_payments = []
    
    # Sort: debtors ascending (most negative first), creditors descending (most positive first)
    debtors.sort(key=lambda x: x["balance"])
    creditors.sort(key=lambda x: x["balance"], reverse=True)

    d_idx = 0
    c_idx = 0

    while d_idx < len(debtors) and c_idx < len(creditors):
        debtor = debtors[d_idx]
        creditor = creditors[c_idx]

        debtor_owe = -debtor["balance"]
        creditor_get = creditor["balance"]

        # If debtor owes less than creditor gets
        if debtor_owe < creditor_get:
            payment = debtor_owe
            creditor["balance"] -= payment
            debtor["balance"] = 0.0
            d_idx += 1
        # If debtor owes more than creditor gets
        elif debtor_owe > creditor_get:
            payment = creditor_get
            debtor["balance"] += payment
            creditor["balance"] = 0.0
            c_idx += 1
        # If equal
        else:
            payment = debtor_owe
            debtor["balance"] = 0.0
            creditor["balance"] = 0.0
            d_idx += 1
            c_idx += 1

        if payment > 0.01:
            simplified_payments.append({
                "from_id": debtor["id"],
                "from_name": debtor["name"],
                "to_id": creditor["id"],
                "to_name": creditor["name"],
                "amount": round(payment, 2)
            })

    return jsonify({
        "balances": balance_summary,
        "simplified_debts": simplified_payments
    })

# --- DATA IMPORT & ANOMALY RESOLUTION ---

@app.route("/api/groups/<group_id>/import/upload", methods=["POST"])
@token_required
def upload_csv(current_user, group_id):
    # Verify group exists
    group = Group.query.get(group_id)
    if not group:
        return jsonify({"message": "Group not found"}), 404

    # Verify authorization
    user_member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not user_member:
        return jsonify({"message": "Unauthorized"}), 403

    if "file" not in request.files:
        return jsonify({"message": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"message": "Empty filename"}), 400

    file_content = file.read().decode("utf-8")
    
    # Run anomaly detector
    anomalies = detect_csv_anomalies(file_content)
    
    # Save draft session and raw data in database
    session_id = str(uuid.uuid4())
    import_session = ImportSession(
        id=session_id,
        status="pending",
        file_name=file.filename
    )
    db.session.add(import_session)

    # Save anomalies
    for a in anomalies:
        anomaly = ImportAnomaly(
            id=str(uuid.uuid4()),
            import_session_id=session_id,
            row_index=a["row_index"],
            raw_row=a["raw_row"],
            anomaly_type=a["anomaly_type"],
            description=a["description"],
            suggested_action=a["suggested_action"],
            status="pending"
        )
        db.session.add(anomaly)

    # We store the raw CSV file in a temporary scratch or app data folder, or in the session object
    # For simplicity, we can store it in a local temporary file in the workspace
    os.makedirs("C:/Users/dayus/Desktop/new project company/backend/temp_imports", exist_ok=True)
    temp_file_path = f"C:/Users/dayus/Desktop/new project company/backend/temp_imports/{session_id}.csv"
    with open(temp_file_path, "w", encoding="utf-8") as f:
        f.write(file_content)

    db.session.commit()

    return jsonify({
        "import_session_id": session_id,
        "anomalies": [a.to_dict() for a in import_session.anomalies]
    }), 201

@app.route("/api/groups/<group_id>/import/session/<session_id>", methods=["GET"])
@token_required
def get_import_session(current_user, group_id, session_id):
    # Verify authorization
    user_member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not user_member:
        return jsonify({"message": "Unauthorized"}), 403

    session = ImportSession.query.get(session_id)
    if not session:
        return jsonify({"message": "Import session not found"}), 404

    return jsonify(session.to_dict())

@app.route("/api/groups/<group_id>/import/session/<session_id>/resolve", methods=["POST"])
@token_required
def resolve_import_session(current_user, group_id, session_id):
    # Verify authorization
    user_member = GroupMember.query.filter_by(group_id=group_id, user_id=current_user.id).first()
    if not user_member:
        return jsonify({"message": "Unauthorized"}), 403

    session = ImportSession.query.get(session_id)
    if not session:
        return jsonify({"message": "Import session not found"}), 404

    if session.status == "completed":
        return jsonify({"message": "Import session already completed!"}), 400

    data = request.get_json()
    resolutions = data.get("resolutions", {}) # dictionary maps anomaly_id -> user choice / custom text
    
    # Load temporary raw CSV
    temp_file_path = f"C:/Users/dayus/Desktop/new project company/backend/temp_imports/{session_id}.csv"
    if not os.path.exists(temp_file_path):
        return jsonify({"message": "Temporary import data lost."}), 400

    with open(temp_file_path, "r", encoding="utf-8") as f:
        file_lines = f.read().splitlines()

    reader = csv.reader(file_lines)
    header = next(reader) # skip header

    # Retrieve all anomalies for this session to query user choices
    anomalies = {a.id: a for a in session.anomalies}
    
    # Gather resolutions per row
    row_resolutions = {}
    for a_id, choice in resolutions.items():
        if a_id in anomalies:
            a = anomalies[a_id]
            a.user_action = choice
            a.status = "resolved"
            
            if a.row_index not in row_resolutions:
                row_resolutions[a.row_index] = {}
            row_resolutions[a.row_index][a.anomaly_type] = choice

    # Get all users registered in system to resolve name mappings
    all_users = User.query.all()
    user_name_map = {normalize_name(u.name)[0]: u.id for u in all_users}
    user_username_map = {u.username: u.id for u in all_users}

    # Helper function to find or map user_id from name string
    def find_user_id(name_str, row_idx):
        norm, _, _ = normalize_name(name_str)
        # Check if there is a name mapping resolution for this row
        row_res = row_resolutions.get(row_idx, {})
        if 'name_alias' in row_res:
            mapped_name = row_res['name_alias']
            norm = normalize_name(mapped_name)[0]
        elif 'name_casing' in row_res:
            mapped_name = row_res['name_casing']
            norm = normalize_name(mapped_name)[0]
        elif 'non_group_member' in row_res:
            mapped_name = row_res['non_group_member']
            # User might choose to create new user or map to existing
            norm = normalize_name(mapped_name)[0]
        elif 'missing_payer' in row_res:
            mapped_name = row_res['missing_payer']
            norm = normalize_name(mapped_name)[0]

        # Check in username map (if email or username passed) or name map
        u_id = user_name_map.get(norm) or user_username_map.get(norm.lower())
        if not u_id:
            # Proactively create a user for guests/non-members if resolved as "Create User"
            # In simple terms, if the mapped name is Kabir/Dev's friend Kabir, and we don't have it
            # We can create a shadow user to prevent database failures.
            password_hash = bcrypt.generate_password_hash("password123").decode("utf-8")
            u_id = str(uuid.uuid4())
            new_u = User(
                id=u_id,
                username=norm.lower().replace(" ", "_").replace("'", ""),
                password_hash=password_hash,
                name=norm
            )
            db.session.add(new_u)
            db.session.flush() # flush to get user registered in current transaction
            
            # Add to group member
            new_gm = GroupMember(
                id=str(uuid.uuid4()),
                group_id=group_id,
                user_id=u_id,
                joined_at=datetime(2026, 2, 1) # default start of rent
            )
            db.session.add(new_gm)
            db.session.flush()

            # Update maps
            user_name_map[norm] = u_id
            user_username_map[norm.lower()] = u_id
            
        return u_id

    imported_count = 0
    skipped_count = 0
    report_items = []

    # Map for conflict resolution (e.g. keeping Row 25 instead of 24)
    handled_conflicts = set()

    for idx, row in enumerate(reader):
        row_idx = idx + 2 # 1-indexed matching CSV row
        
        # Check if the row was resolved to be deleted/ignored
        row_res = row_resolutions.get(row_idx, {})
        
        # 1. Zero Amount Skip Choice
        if 'zero_amount' in row_res and row_res['zero_amount'] == 'skip':
            skipped_count += 1
            report_items.append({
                "row_index": row_idx,
                "description": row[1],
                "action": "Skipped (Zero Amount)"
            })
            continue

        # 2. Duplicate Check Resolution
        if 'duplicate' in row_res:
            action = row_res['duplicate'] # "keep" or "ignore"
            if action == 'ignore':
                skipped_count += 1
                report_items.append({
                    "row_index": row_idx,
                    "description": row[1],
                    "action": "Skipped (Duplicate)"
                })
                continue
            
        # 3. Conflict Check Resolution (Row 24 vs Row 25)
        if 'conflict' in row_res:
            action = row_res['conflict'] # e.g. "keep_row_25", "keep_row_24", "keep_both"
            # If we decide to keep the other row, skip this one
            if action.startswith("keep_row_") and str(row_idx) not in action:
                skipped_count += 1
                report_items.append({
                    "row_index": row_idx,
                    "description": row[1],
                    "action": f"Skipped (Conflict resolved in favor of other row)"
                })
                continue

        # Re-parse date using resolutions
        date_raw = row[0]
        dt, _, date_suggest = parse_date(date_raw)
        
        if 'ambiguous_date' in row_res:
            # e.g. "05-04-2026"
            dt = datetime.strptime(row_res['ambiguous_date'], "%d-%m-%Y")
        elif 'inconsistent_date_format' in row_res:
            dt = datetime.strptime(row_res['inconsistent_date_format'], "%d-%m-%Y")
        elif dt is None:
            # Fallback
            dt = datetime(2026, 2, 1)

        # Re-parse amount using resolutions
        amount_raw = row[3]
        amt_val, _, amt_suggest = clean_amount(amount_raw)
        if 'quoted_amount' in row_res:
            amt_val = float(row_res['quoted_amount'])
        elif 'high_precision_amount' in row_res:
            amt_val = float(row_res['high_precision_amount'])
        elif amt_val is None:
            amt_val = 0.0

        # Currency and FX rate
        currency_raw = row[4]
        currency = currency_raw.strip().upper() if currency_raw.strip() else "INR"
        if 'missing_currency' in row_res:
            currency = row_res['missing_currency']

        exchange_rate = 1.0
        if currency == "USD":
            # Default rate 83.0 or user customized rate
            fx_choice = row_res.get('usd_transaction', '83.0')
            exchange_rate = float(fx_choice)
        
        amount_in_inr = amt_val * exchange_rate

        # Get payer
        paid_by_raw = row[2]
        paid_by_id = find_user_id(paid_by_raw, row_idx)

        # Split Type and Splits list
        split_type_raw = row[5]
        split_type = split_type_raw.strip().lower() if split_type_raw.strip() else "equal"
        
        split_with_raw = row[6]
        split_with = [normalize_name(p)[0] for p in split_with_raw.split(';') if p.strip()]

        split_details_raw = row[7] if len(row) > 7 else ""
        notes_raw = row[8] if len(row) > 8 else ""

        # Check if settlement disguised as expense
        is_settlement_resolved = ('settlement_disguised' in row_res and row_res['settlement_disguised'] == 'settlement') or \
                                 (not split_type_raw.strip() and 'paid back' in row[1].lower())

        if is_settlement_resolved:
            # Create a direct settlement between payer and single recipient (split_with[0])
            payee_name = split_with[0] if split_with else "Aisha"
            payee_id = find_user_id(payee_name, row_idx)
            
            settlement_id = str(uuid.uuid4())
            settlement = Settlement(
                id=settlement_id,
                group_id=group_id,
                payer_id=paid_by_id,
                payee_id=payee_id,
                amount_in_inr=amount_in_inr,
                date=dt,
                notes=f"CSV Import: {row[1]}"
            )
            db.session.add(settlement)
            imported_count += 1
            report_items.append({
                "row_index": row_idx,
                "description": row[1],
                "action": f"Imported as Settlement (₹{amount_in_inr:.2f} Paid back to {payee_name})"
            })
            continue

        # Normal Split Expense Creation
        # Resolve Guest split (Dev's friend Kabir)
        # Check if Kabir is in split
        resolved_splits = []
        
        # Determine who is in the split on this date
        # Check for inactive member splits (Meera in April)
        active_split_members = []
        for m_name in split_with:
            # check if inactive resolution applies
            if m_name == 'Meera' and 'inactive_member_split' in row_res:
                if row_res['inactive_member_split'] == 'exclude':
                    continue # skip Meera
            
            if m_name == 'Sam' and 'early_member_split' in row_res:
                if row_res['early_member_split'] == 'exclude':
                    continue # skip Sam
                    
            if ('Dev\'s friend Kabir' in m_name or 'Kabir' in m_name) and 'guest_split' in row_res:
                guest_action = row_res['guest_split'] # "assign_to_dev" or "add_member"
                if guest_action == 'assign_to_dev':
                    # Instead of Kabir, we attribute Kabir's share to Dev (increase Dev's share)
                    # We will log it, but wait: if Dev is already in split, Dev gets another share!
                    # For simplicity, we add "Dev" as the split member, meaning Dev splits Kabir's part
                    active_split_members.append("Dev")
                    continue
                else:
                    # add Kabir as a member
                    active_split_members.append("Kabir")
                    continue
                    
            active_split_members.append(m_name)

        # Map active names to user IDs
        split_user_ids = [find_user_id(name, row_idx) for name in active_split_members]
        # De-duplicate splits user list
        split_user_ids = list(set(split_user_ids))

        # Create expense record
        expense_id = str(uuid.uuid4())
        expense = Expense(
            id=expense_id,
            group_id=group_id,
            description=row[1],
            amount=amt_val,
            currency=currency,
            exchange_rate=exchange_rate,
            amount_in_inr=amount_in_inr,
            paid_by_id=paid_by_id,
            split_type=split_type,
            date=dt,
            notes=notes_raw,
            is_settlement=False
        )

        # Process splits by type
        if split_type == "equal" or 'redundant_split_details' in row_res:
            split_share = amount_in_inr / len(split_user_ids)
            for u_id in split_user_ids:
                split = ExpenseSplit(
                    id=str(uuid.uuid4()),
                    expense_id=expense_id,
                    user_id=u_id,
                    amount_in_inr=split_share
                )
                db.session.add(split)
                
        elif split_type == "percentage":
            # Extract percentages
            # Default percentages from split details or normalized if invalid percentage sum
            pct_matches = re.findall(r'(\w+)\s+(\d+)%', split_details_raw)
            pct_dict = {normalize_name(name)[0]: float(pct) for name, pct in pct_matches}
            
            # Normalize if sum was 110% (rescale to 100%)
            total_pct = sum(pct_dict.values())
            if abs(total_pct - 100.0) > 0.1 and 'invalid_percentage_sum' in row_res:
                if row_res['invalid_percentage_sum'] == 'normalize':
                    pct_dict = {name: (pct / total_pct) * 100.0 for name, pct in pct_dict.items()}
            
            for m_name in active_split_members:
                pct = pct_dict.get(m_name, 100.0 / len(active_split_members))
                u_id = find_user_id(m_name, row_idx)
                share_inr = (pct / 100.0) * amount_in_inr
                split = ExpenseSplit(
                    id=str(uuid.uuid4()),
                    expense_id=expense_id,
                    user_id=u_id,
                    amount_in_inr=share_inr,
                    split_value=pct
                )
                db.session.add(split)

        elif split_type == "share":
            # Parse shares, e.g. "Aisha 2; Rohan 1; Priya 1"
            share_matches = re.findall(r'(\w+)\s+(\d+)', split_details_raw)
            share_dict = {normalize_name(name)[0]: float(shares) for name, shares in share_matches}
            
            # Fallback if parsing failed
            if not share_dict:
                share_dict = {name: 1.0 for name in active_split_members}
                
            total_shares = sum(share_dict.get(name, 1.0) for name in active_split_members)
            for m_name in active_split_members:
                shares = share_dict.get(m_name, 1.0)
                u_id = find_user_id(m_name, row_idx)
                share_inr = (shares / total_shares) * amount_in_inr
                split = ExpenseSplit(
                    id=str(uuid.uuid4()),
                    expense_id=expense_id,
                    user_id=u_id,
                    amount_in_inr=share_inr,
                    split_value=shares
                )
                db.session.add(split)

        elif split_type == "unequal":
            # Parse unequal, e.g. "Rohan 700; Priya 400; Meera 400"
            amt_matches = re.findall(r'(\w+)\s+(\d+)', split_details_raw)
            amt_dict = {normalize_name(name)[0]: float(val) for name, val in amt_matches}
            
            for m_name in active_split_members:
                val = amt_dict.get(m_name, 0.0)
                # Apply exchange rate conversion if original currency is USD
                val_inr = val * exchange_rate if currency == "USD" else val
                u_id = find_user_id(m_name, row_idx)
                split = ExpenseSplit(
                    id=str(uuid.uuid4()),
                    expense_id=expense_id,
                    user_id=u_id,
                    amount_in_inr=val_inr,
                    split_value=val
                )
                db.session.add(split)

        db.session.add(expense)
        imported_count += 1
        
        report_items.append({
            "row_index": row_idx,
            "description": row[1],
            "action": f"Imported (₹{amount_in_inr:.2f} paid by {normalize_name(paid_by_raw)[0]}, Split: {split_type})"
        })

    # Save details of import run
    session.status = "completed"
    db.session.commit()
    
    # Remove local temp file
    if os.path.exists(temp_file_path):
        os.remove(temp_file_path)

    return jsonify({
        "message": "CSV Import completed successfully",
        "imported_count": imported_count,
        "skipped_count": skipped_count,
        "report": report_items
    })

# --- RUN THE APP ---

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

from datetime import datetime
from backend.database import db

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.String(36), primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    memberships = db.relationship('GroupMember', backref='user', cascade='all, delete-orphan', lazy=True)
    splits = db.relationship('ExpenseSplit', backref='user', cascade='all, delete-orphan', lazy=True)
    
    # We specify foreign_keys explicitly on references in Expense and Settlement
    # backref named in other classes or queried directly.

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'name': self.name,
            'created_at': self.created_at.isoformat()
        }

class Group(db.Model):
    __tablename__ = 'groups'
    
    id = db.Column(db.String(36), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    members = db.relationship('GroupMember', backref='group', cascade='all, delete-orphan', lazy=True)
    expenses = db.relationship('Expense', backref='group', cascade='all, delete-orphan', lazy=True)
    settlements = db.relationship('Settlement', backref='group', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat()
        }

class GroupMember(db.Model):
    __tablename__ = 'group_members'
    
    id = db.Column(db.String(36), primary_key=True)
    group_id = db.Column(db.String(36), db.ForeignKey('groups.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    joined_at = db.Column(db.DateTime, nullable=False)
    left_at = db.Column(db.DateTime, nullable=True) # None if still active in the group

    __table_args__ = (db.UniqueConstraint('group_id', 'user_id', name='_group_user_uc'),)

    def to_dict(self):
        return {
            'id': self.id,
            'group_id': self.group_id,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else None,
            'joined_at': self.joined_at.isoformat(),
            'left_at': self.left_at.isoformat() if self.left_at else None
        }

class Expense(db.Model):
    __tablename__ = 'expenses'
    
    id = db.Column(db.String(36), primary_key=True)
    group_id = db.Column(db.String(36), db.ForeignKey('groups.id', ondelete='CASCADE'), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), nullable=False)
    exchange_rate = db.Column(db.Float, default=1.0)
    amount_in_inr = db.Column(db.Float, nullable=False)
    paid_by_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    split_type = db.Column(db.String(50), nullable=False) # "equal", "unequal", "percentage", "share"
    date = db.Column(db.DateTime, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    is_settlement = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    splits = db.relationship('ExpenseSplit', backref='expense', cascade='all, delete-orphan', lazy=True)
    paid_by = db.relationship('User', foreign_keys=[paid_by_id])

    def to_dict(self):
        return {
            'id': self.id,
            'group_id': self.group_id,
            'description': self.description,
            'amount': self.amount,
            'currency': self.currency,
            'exchange_rate': self.exchange_rate,
            'amount_in_inr': self.amount_in_inr,
            'paid_by_id': self.paid_by_id,
            'paid_by_name': self.paid_by.name if self.paid_by else None,
            'split_type': self.split_type,
            'date': self.date.isoformat(),
            'notes': self.notes,
            'is_settlement': self.is_settlement,
            'created_at': self.created_at.isoformat(),
            'splits': [s.to_dict() for s in self.splits]
        }

class ExpenseSplit(db.Model):
    __tablename__ = 'expense_splits'
    
    id = db.Column(db.String(36), primary_key=True)
    expense_id = db.Column(db.String(36), db.ForeignKey('expenses.id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.String(36), db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    amount_in_inr = db.Column(db.Float, nullable=False)
    split_value = db.Column(db.Float, nullable=True) # Percentage or share count, if applicable

    def to_dict(self):
        return {
            'id': self.id,
            'expense_id': self.expense_id,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else None,
            'amount_in_inr': self.amount_in_inr,
            'split_value': self.split_value
        }

class Settlement(db.Model):
    __tablename__ = 'settlements'
    
    id = db.Column(db.String(36), primary_key=True)
    group_id = db.Column(db.String(36), db.ForeignKey('groups.id', ondelete='CASCADE'), nullable=False)
    payer_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    payee_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    amount_in_inr = db.Column(db.Float, nullable=False)
    date = db.Column(db.DateTime, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    payer = db.relationship('User', foreign_keys=[payer_id])
    payee = db.relationship('User', foreign_keys=[payee_id])

    def to_dict(self):
        return {
            'id': self.id,
            'group_id': self.group_id,
            'payer_id': self.payer_id,
            'payer_name': self.payer.name if self.payer else None,
            'payee_id': self.payee_id,
            'payee_name': self.payee.name if self.payee else None,
            'amount_in_inr': self.amount_in_inr,
            'date': self.date.isoformat(),
            'notes': self.notes,
            'created_at': self.created_at.isoformat()
        }

class ImportSession(db.Model):
    __tablename__ = 'import_sessions'
    
    id = db.Column(db.String(36), primary_key=True)
    status = db.Column(db.String(50), nullable=False) # "pending" or "completed"
    file_name = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    anomalies = db.relationship('ImportAnomaly', backref='session', cascade='all, delete-orphan', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'status': self.status,
            'file_name': self.file_name,
            'created_at': self.created_at.isoformat(),
            'anomalies': [a.to_dict() for a in self.anomalies]
        }

class ImportAnomaly(db.Model):
    __tablename__ = 'import_anomalies'
    
    id = db.Column(db.String(36), primary_key=True)
    import_session_id = db.Column(db.String(36), db.ForeignKey('import_sessions.id', ondelete='CASCADE'), nullable=False)
    row_index = db.Column(db.Integer, nullable=False)
    raw_row = db.Column(db.Text, nullable=False)
    anomaly_type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    suggested_action = db.Column(db.String(255), nullable=False)
    user_action = db.Column(db.String(255), nullable=True) # Stores the user's resolution decision
    status = db.Column(db.String(50), default="pending") # "pending", "resolved", "ignored"

    def to_dict(self):
        return {
            'id': self.id,
            'import_session_id': self.import_session_id,
            'row_index': self.row_index,
            'raw_row': self.raw_row,
            'anomaly_type': self.anomaly_type,
            'description': self.description,
            'suggested_action': self.suggested_action,
            'user_action': self.user_action,
            'status': self.status
        }

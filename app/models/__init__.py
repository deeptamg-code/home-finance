from flask_login import UserMixin

from datetime import datetime

from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db


class User(UserMixin,db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(80), nullable=False)

    email = db.Column(
        db.String(120),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(db.String(255), nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    # Save a securely hashed password
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # Check the entered password
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"



class FinancialSettings(db.Model):
    __tablename__ = "financial_settings"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        unique=True,
        nullable=False
    )

    # This application uses Japanese Yen only
    currency = db.Column(
        db.String(3),
        nullable=False,
        default="JPY"
    )

    # Initial cash balance
    opening_cash_balance = db.Column(
        db.Numeric(15, 2),
        nullable=False,
        default=0
    )

    user = db.relationship(
        "User",
        backref=db.backref("financial_settings", uselist=False)
    )


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    category_type = db.Column(
        db.String(20),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user = db.relationship(
        "User",
        backref="categories"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "name",
            "category_type",
            name="uq_user_category_name_type"
        ),
        db.CheckConstraint(
            "category_type IN ('income', 'expense')",
            name="ck_category_type"
        ),
    )

    def __repr__(self):
        return f"<Category {self.name}>"


class Income(db.Model):
    __tablename__ = "incomes"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id"),
        nullable=False
    )

    title = db.Column(
        db.String(150),
        nullable=False
    )

    amount = db.Column(
        db.Numeric(15, 2),
        nullable=False
    )

    income_date = db.Column(
        db.Date,
        nullable=False
    )

    note = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user = db.relationship(
        "User",
        backref="incomes"
    )

    category = db.relationship(
        "Category",
        backref="incomes"
    )

    __table_args__ = (
        db.CheckConstraint(
            "amount > 0",
            name="ck_income_amount_positive"
        ),
    )

    def __repr__(self):
        return f"<Income {self.title}: {self.amount}>"



class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    category_id = db.Column(
        db.Integer,
        db.ForeignKey("categories.id"),
        nullable=False
    )

    title = db.Column(
        db.String(150),
        nullable=False
    )

    amount = db.Column(
        db.Numeric(15, 2),
        nullable=False
    )

    expense_date = db.Column(
        db.Date,
        nullable=False
    )

    note = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user = db.relationship(
        "User",
        backref="expenses"
    )

    category = db.relationship(
        "Category",
        backref="expenses"
    )

    __table_args__ = (
        db.CheckConstraint(
            "amount > 0",
            name="ck_expense_amount_positive"
        ),
    )

    def __repr__(self):
        return f"<Expense {self.title}: {self.amount}>"


class Loan(db.Model):
    __tablename__ = "loans"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    # personal / bank / finance
    loan_type = db.Column(
        db.String(30),
        nullable=False
    )

    # borrowed / lent
    direction = db.Column(
        db.String(20),
        nullable=False
    )

    # Person, bank, or finance company
    counterparty = db.Column(
        db.String(150),
        nullable=False
    )

    # Original loan amount in JPY
    principal_amount = db.Column(
        db.Numeric(15, 2),
        nullable=False
    )

    # Store percentage: 2.00 means 2% per month
    monthly_interest_rate = db.Column(
        db.Numeric(7, 4),
        nullable=False,
        default=0
    )

    # flexible / four_installments
    repayment_method = db.Column(
        db.String(30),
        nullable=False
    )

    loan_date = db.Column(
        db.Date,
        nullable=False
    )

    first_due_date = db.Column(
        db.Date,
        nullable=True
    )

    installment_count = db.Column(
        db.Integer,
        nullable=False,
        default=4
    )

    note = db.Column(
        db.Text,
        nullable=True
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user = db.relationship(
        "User",
        backref="loans"
    )

    __table_args__ = (
        db.CheckConstraint(
            "loan_type IN ('personal', 'bank', 'finance')",
            name="ck_loan_type"
        ),
        db.CheckConstraint(
            "direction IN ('borrowed', 'lent')",
            name="ck_loan_direction"
        ),
        db.CheckConstraint(
            "principal_amount > 0",
            name="ck_loan_principal_positive"
        ),
        db.CheckConstraint(
            "monthly_interest_rate >= 0",
            name="ck_loan_interest_rate"
        ),
        db.CheckConstraint(
            "repayment_method IN ('flexible', 'four_installments')",
            name="ck_loan_repayment_method"
        ),
        db.CheckConstraint(
            "installment_count > 0",
            name="ck_loan_installment_count"
        ),
    )

    def __repr__(self):
        return f"<Loan {self.direction}: {self.principal_amount}>"



class LoanInterestAccrual(db.Model):
    __tablename__ = "loan_interest_accruals"

    id = db.Column(db.Integer, primary_key=True)

    loan_id = db.Column(
        db.Integer,
        db.ForeignKey("loans.id"),
        nullable=False
    )

    period_start = db.Column(
        db.Date,
        nullable=False
    )

    # Outstanding principal when interest was calculated
    principal_basis = db.Column(
        db.Numeric(15, 2),
        nullable=False
    )

    interest_rate = db.Column(
        db.Numeric(7, 4),
        nullable=False
    )

    interest_amount = db.Column(
        db.Numeric(15, 2),
        nullable=False
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    loan = db.relationship(
        "Loan",
        backref="interest_accruals"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "loan_id",
            "period_start",
            name="uq_loan_interest_period"
        ),
        db.CheckConstraint(
            "principal_basis >= 0",
            name="ck_interest_principal_basis"
        ),
        db.CheckConstraint(
            "interest_rate >= 0",
            name="ck_interest_rate"
        ),
        db.CheckConstraint(
            "interest_amount >= 0",
            name="ck_interest_amount"
        ),
    )


class LoanInstallment(db.Model):
    __tablename__ = "loan_installments"

    id = db.Column(db.Integer, primary_key=True)

    loan_id = db.Column(
        db.Integer,
        db.ForeignKey("loans.id"),
        nullable=False
    )

    installment_number = db.Column(
        db.Integer,
        nullable=False
    )

    principal_due = db.Column(
        db.Numeric(15, 2),
        nullable=False
    )

    interest_due = db.Column(
        db.Numeric(15, 2),
        nullable=False,
        default=0
    )

    due_date = db.Column(
        db.Date,
        nullable=False
    )

    status = db.Column(
        db.String(20),
        nullable=False,
        default="pending"
    )

    loan = db.relationship(
        "Loan",
        backref="installments"
    )

    __table_args__ = (
        db.UniqueConstraint(
            "loan_id",
            "installment_number",
            name="uq_loan_installment_number"
        ),
        db.CheckConstraint(
            "installment_number > 0",
            name="ck_installment_number"
        ),
        db.CheckConstraint(
            "principal_due >= 0",
            name="ck_installment_principal"
        ),
        db.CheckConstraint(
            "interest_due >= 0",
            name="ck_installment_interest"
        ),
        db.CheckConstraint(
            "status IN ('pending', 'partial', 'paid', 'overdue')",
            name="ck_installment_status"
        ),
    )

    def __repr__(self):
        return f"<LoanInstallment {self.installment_number}: {self.status}>"


class LoanPayment(db.Model):
    __tablename__ = "loan_payments"

    id = db.Column(db.Integer, primary_key=True)

    loan_id = db.Column(
        db.Integer,
        db.ForeignKey("loans.id"),
        nullable=False
    )

    # NULL for flexible loan payments
    installment_id = db.Column(
        db.Integer,
        db.ForeignKey("loan_installments.id"),
        nullable=True
    )

    principal_paid = db.Column(
        db.Numeric(15, 2),
        nullable=False,
        default=0
    )

    interest_paid = db.Column(
        db.Numeric(15, 2),
        nullable=False,
        default=0
    )

    payment_date = db.Column(
        db.Date,
        nullable=False
    )

    note = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    loan = db.relationship(
        "Loan",
        backref="payments"
    )

    installment = db.relationship(
        "LoanInstallment",
        backref="payments"
    )

    __table_args__ = (
        db.CheckConstraint(
            "principal_paid >= 0",
            name="ck_payment_principal"
        ),
        db.CheckConstraint(
            "interest_paid >= 0",
            name="ck_payment_interest"
        ),
        db.CheckConstraint(
            "principal_paid + interest_paid > 0",
            name="ck_payment_total_positive"
        ),
    )

    def __repr__(self):
        return f"<LoanPayment {self.id}: {self.principal_paid + self.interest_paid}>"


class SavingsGoal(db.Model):
    __tablename__ = "savings_goals"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    name = db.Column(
        db.String(100),
        nullable=False
    )

    target_amount = db.Column(
        db.Numeric(15, 2),
        nullable=False,
        default=0
    )

    opening_balance = db.Column(
        db.Numeric(15, 2),
        nullable=False,
        default=0
    )

    description = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user = db.relationship(
        "User",
        backref="savings_goals"
    )

    __table_args__ = (
        db.CheckConstraint(
            "target_amount >= 0",
            name="ck_savings_goal_target"
        ),
        db.CheckConstraint(
            "opening_balance >= 0",
            name="ck_savings_goal_opening_balance"
        ),
    )

    def __repr__(self):
        return f"<SavingsGoal {self.name}>"


class SavingsTransaction(db.Model):
    __tablename__ = "savings_transactions"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    goal_id = db.Column(
        db.Integer,
        db.ForeignKey("savings_goals.id"),
        nullable=False
    )

    transaction_type = db.Column(
        db.String(20),
        nullable=False
    )

    amount = db.Column(
        db.Numeric(15, 2),
        nullable=False
    )

    transaction_date = db.Column(
        db.Date,
        nullable=False
    )

    note = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )

    user = db.relationship(
        "User",
        backref="savings_transactions"
    )

    goal = db.relationship(
        "SavingsGoal",
        backref="transactions"
    )

    __table_args__ = (
        db.CheckConstraint(
            "transaction_type IN ('deposit', 'withdrawal')",
            name="ck_savings_transaction_type"
        ),
        db.CheckConstraint(
            "amount > 0",
            name="ck_savings_transaction_amount"
        ),
    )

    def __repr__(self):
        return f"<SavingsTransaction {self.id}: {self.transaction_type}>"

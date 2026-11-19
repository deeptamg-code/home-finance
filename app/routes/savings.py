
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.routes import savings_bp
from app.models import SavingsGoal, SavingsTransaction


# --------------------------------------------------
# Helper: Calculate the current balance of a goal
# --------------------------------------------------
def get_goal_balance(goal):

    deposits = (
        db.session.query(db.func.coalesce(db.func.sum(SavingsTransaction.amount), 0))
        .filter_by(
            goal_id=goal.id,
            user_id=current_user.id,
            transaction_type="deposit"
        )
        .scalar()
    )

    withdrawals = (
        db.session.query(db.func.coalesce(db.func.sum(SavingsTransaction.amount), 0))
        .filter_by(
            goal_id=goal.id,
            user_id=current_user.id,
            transaction_type="withdrawal"
        )
        .scalar()
    )

    opening_balance = goal.opening_balance or Decimal("0")

    return (
        Decimal(str(opening_balance))
        + Decimal(str(deposits))
        - Decimal(str(withdrawals))
    )


# --------------------------------------------------
# Savings Goals: List
# --------------------------------------------------
@savings_bp.route("/")
@login_required
def index():

    goals = SavingsGoal.query.filter_by(
        user_id=current_user.id
    ).order_by(SavingsGoal.id.desc()).all()

    goal_balances = {
        goal.id: get_goal_balance(goal)
        for goal in goals
    }

    return render_template(
        "savings/index.html",
        goals=goals,
        goal_balances=goal_balances
    )


# --------------------------------------------------
# Savings Goals: Add
# --------------------------------------------------
@savings_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        try:
            target_amount = Decimal(
                request.form.get("target_amount", "0").strip()
            )
            opening_balance = Decimal(
                request.form.get("opening_balance", "0").strip()
            )

            if not target_amount.is_finite() or not opening_balance.is_finite():
                raise InvalidOperation

        except (InvalidOperation, ValueError):
            flash("Please enter valid amounts.", "danger")
            return redirect(url_for("savings.add"))

        if not name:
            flash("Please enter a savings goal name.", "danger")
            return redirect(url_for("savings.add"))

        if target_amount <= 0:
            flash("Target amount must be greater than zero.", "danger")
            return redirect(url_for("savings.add"))

        if opening_balance < 0:
            flash("Opening balance cannot be negative.", "danger")
            return redirect(url_for("savings.add"))

        goal = SavingsGoal(
            user_id=current_user.id,
            name=name,
            target_amount=target_amount,
            opening_balance=opening_balance,
            description=description
        )

        db.session.add(goal)
        db.session.commit()

        flash("Savings goal added successfully!", "success")
        return redirect(url_for("savings.index"))

    return render_template("savings/add.html")


# --------------------------------------------------
# Savings Goals: Edit
# --------------------------------------------------
@savings_bp.route("/<int:goal_id>/edit", methods=["GET", "POST"])
@login_required
def edit(goal_id):

    goal = SavingsGoal.query.filter_by(
        id=goal_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        try:
            target_amount = Decimal(
                request.form.get("target_amount", "0").strip()
            )
            opening_balance = Decimal(
                request.form.get("opening_balance", "0").strip()
            )

            if not target_amount.is_finite() or not opening_balance.is_finite():
                raise InvalidOperation

        except (InvalidOperation, ValueError):
            flash("Please enter valid amounts.", "danger")
            return redirect(url_for("savings.edit", goal_id=goal.id))

        if not name:
            flash("Please enter a savings goal name.", "danger")
            return redirect(url_for("savings.edit", goal_id=goal.id))

        if target_amount <= 0:
            flash("Target amount must be greater than zero.", "danger")
            return redirect(url_for("savings.edit", goal_id=goal.id))

        if opening_balance < 0:
            flash("Opening balance cannot be negative.", "danger")
            return redirect(url_for("savings.edit", goal_id=goal.id))

        goal.name = name
        goal.target_amount = target_amount
        goal.opening_balance = opening_balance
        goal.description = description

        db.session.commit()

        flash("Savings goal updated successfully!", "success")
        return redirect(url_for("savings.index"))

    return render_template(
        "savings/edit.html",
        goal=goal
    )


# --------------------------------------------------
# Savings Goals: Delete
# Only goals without transaction history can be deleted.
# --------------------------------------------------
@savings_bp.route("/<int:goal_id>/delete", methods=["POST"])
@login_required
def delete(goal_id):

    goal = SavingsGoal.query.filter_by(
        id=goal_id,
        user_id=current_user.id
    ).first_or_404()

    has_transactions = SavingsTransaction.query.filter_by(
        goal_id=goal.id,
        user_id=current_user.id
    ).first()

    if has_transactions:
        flash(
            "This goal cannot be deleted because it has transaction history.",
            "danger"
        )
        return redirect(url_for("savings.index"))

    db.session.delete(goal)
    db.session.commit()

    flash("Savings goal deleted successfully!", "success")
    return redirect(url_for("savings.index"))


# --------------------------------------------------
# Savings Goals: Deposit / Withdrawal
# --------------------------------------------------
@savings_bp.route("/<int:goal_id>/transaction", methods=["GET", "POST"])
@login_required
def transaction(goal_id):

    goal = SavingsGoal.query.filter_by(
        id=goal_id,
        user_id=current_user.id
    ).first_or_404()

    current_balance = get_goal_balance(goal)

    if request.method == "POST":

        transaction_type = request.form.get("transaction_type", "").strip()
        note = request.form.get("note", "").strip()

        try:
            amount = Decimal(
                request.form.get("amount", "0").strip()
            )

            if not amount.is_finite():
                raise InvalidOperation

        except (InvalidOperation, ValueError):
            flash("Please enter a valid amount.", "danger")
            return redirect(
                url_for("savings.transaction", goal_id=goal.id)
            )

        if transaction_type not in ["deposit", "withdrawal"]:
            flash("Please select a valid transaction type.", "danger")
            return redirect(
                url_for("savings.transaction", goal_id=goal.id)
            )

        if amount <= 0:
            flash("Amount must be greater than zero.", "danger")
            return redirect(
                url_for("savings.transaction", goal_id=goal.id)
            )

        if transaction_type == "withdrawal" and amount > current_balance:
            flash("Withdrawal amount cannot exceed the current balance.", "danger")
            return redirect(
                url_for("savings.transaction", goal_id=goal.id)
            )

        new_transaction = SavingsTransaction(
            user_id=current_user.id,
            goal_id=goal.id,
            transaction_type=transaction_type,
            amount=amount,
            transaction_date=date.today(),
            note=note
        )

        db.session.add(new_transaction)
        db.session.commit()

        flash("Savings transaction added successfully!", "success")
        return redirect(url_for("savings.index"))

    return render_template(
        "savings/transaction.html",
        goal=goal,
        current_balance=current_balance
    )


# --------------------------------------------------
# Savings Goals: Transaction History
# --------------------------------------------------
@savings_bp.route("/<int:goal_id>/history")
@login_required
def history(goal_id):

    goal = SavingsGoal.query.filter_by(
        id=goal_id,
        user_id=current_user.id
    ).first_or_404()

    transactions = (
        SavingsTransaction.query
        .filter_by(
            goal_id=goal.id,
            user_id=current_user.id
        )
        .order_by(
            SavingsTransaction.transaction_date.desc(),
            SavingsTransaction.id.desc()
        )
        .all()
    )

    current_balance = get_goal_balance(goal)

    return render_template(
        "savings/history.html",
        goal=goal,
        transactions=transactions,
        current_balance=current_balance
    )

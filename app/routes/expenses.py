
from datetime import date
from decimal import Decimal, InvalidOperation

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash
)
from flask_login import login_required, current_user

from app.routes import expenses_bp
from app.extensions import db
from app.models import Expense, Category


# ==========================================
# Get expense categories
# ==========================================
def get_expense_categories():

    categories = Category.query.filter_by(
        user_id=current_user.id,
        category_type="expense"
    ).all()

    # Create default categories if none exist
    if not categories:

        default_categories = [
            "Food",
            "Transportation",
            "Rent",
            "Utilities",
            "Shopping",
            "Entertainment",
            "Other"
        ]

        for name in default_categories:
            db.session.add(
                Category(
                    user_id=current_user.id,
                    name=name,
                    category_type="expense"
                )
            )

        db.session.commit()

    return (
        Category.query
        .filter_by(
            user_id=current_user.id,
            category_type="expense"
        )
        .order_by(Category.name.asc())
        .all()
    )


# ==========================================
# Validate expense form
# ==========================================
def validate_expense_form():

    title = request.form.get("title", "").strip()
    category_id = request.form.get("category_id", type=int)
    amount_text = request.form.get("amount", "").strip()
    expense_date_text = request.form.get("expense_date", "").strip()
    note = request.form.get("note", "").strip()

    if not title:
        return None, "Please enter an expense title."

    category = Category.query.filter_by(
        id=category_id,
        user_id=current_user.id,
        category_type="expense"
    ).first()

    if not category:
        return None, "Please select a valid expense category."

    try:
        amount = Decimal(amount_text)

        if not amount.is_finite() or amount <= 0:
            raise InvalidOperation

        amount = amount.quantize(Decimal("0.01"))

    except (InvalidOperation, ValueError):
        return None, "Please enter a valid amount greater than zero."

    try:
        expense_date = date.fromisoformat(expense_date_text)

    except ValueError:
        return None, "Please enter a valid expense date."

    return {
        "title": title,
        "category": category,
        "amount": amount,
        "expense_date": expense_date,
        "note": note if note else None
    }, None


# ==========================================
# Expense History
# ==========================================
@expenses_bp.route("/")
@login_required
def index():

    expenses = (
        Expense.query
        .filter_by(user_id=current_user.id)
        .order_by(
            Expense.expense_date.desc(),
            Expense.id.desc()
        )
        .all()
    )

    return render_template(
        "expenses/index.html",
        expenses=expenses
    )


# ==========================================
# Add Expense
# ==========================================
@expenses_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():

    categories = get_expense_categories()

    if request.method == "POST":

        data, error = validate_expense_form()

        if error:
            flash(error, "danger")

            return render_template(
                "expenses/add.html",
                categories=categories,
                expense=None
            )

        expense = Expense(
            user_id=current_user.id,
            category_id=data["category"].id,
            title=data["title"],
            amount=data["amount"],
            expense_date=data["expense_date"],
            note=data["note"]
        )

        try:
            db.session.add(expense)
            db.session.commit()

            flash("Expense added successfully!", "success")

            return redirect(url_for("expenses.index"))

        except Exception:
            db.session.rollback()

            flash(
                "Could not save expense. Please try again.",
                "danger"
            )

    return render_template(
        "expenses/add.html",
        categories=categories,
        expense=None
    )


# ==========================================
# Edit Expense
# ==========================================
@expenses_bp.route(
    "/<int:expense_id>/edit",
    methods=["GET", "POST"]
)
@login_required
def edit(expense_id):

    expense = Expense.query.filter_by(
        id=expense_id,
        user_id=current_user.id
    ).first_or_404()

    categories = get_expense_categories()

    if request.method == "POST":

        data, error = validate_expense_form()

        if error:
            flash(error, "danger")

            return render_template(
                "expenses/add.html",
                categories=categories,
                expense=expense
            )

        expense.category_id = data["category"].id
        expense.title = data["title"]
        expense.amount = data["amount"]
        expense.expense_date = data["expense_date"]
        expense.note = data["note"]

        try:
            db.session.commit()

            flash("Expense updated successfully!", "success")

            return redirect(url_for("expenses.index"))

        except Exception:
            db.session.rollback()

            flash(
                "Could not update expense. Please try again.",
                "danger"
            )

    return render_template(
        "expenses/add.html",
        categories=categories,
        expense=expense
    )


# ==========================================
# Delete Expense
# ==========================================
@expenses_bp.route(
    "/<int:expense_id>/delete",
    methods=["POST"]
)
@login_required
def delete(expense_id):

    expense = Expense.query.filter_by(
        id=expense_id,
        user_id=current_user.id
    ).first_or_404()

    try:
        db.session.delete(expense)
        db.session.commit()

        flash("Expense deleted successfully!", "success")

    except Exception:
        db.session.rollback()

        flash(
            "Could not delete expense. Please try again.",
            "danger"
        )

    return redirect(url_for("expenses.index"))

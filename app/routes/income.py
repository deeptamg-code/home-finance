
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

from app.routes import income_bp
from app.extensions import db
from app.models import Income, Category


def get_income_categories():
    """Get this user's income categories, creating defaults if needed."""

    categories = Category.query.filter_by(
        user_id=current_user.id,
        category_type="income"
    ).all()

    if not categories:
        default_categories = [
            "Salary",
            "Part-time Job",
            "Business",
            "Bonus",
            "Other"
        ]

        for name in default_categories:
            db.session.add(Category(
                user_id=current_user.id,
                name=name,
                category_type="income"
            ))

        db.session.commit()

    return (
        Category.query
        .filter_by(
            user_id=current_user.id,
            category_type="income"
        )
        .order_by(Category.name.asc())
        .all()
    )


def validate_income_form():
    """Validate submitted income data."""

    title = request.form.get("title", "").strip()
    category_id = request.form.get("category_id", type=int)
    amount_text = request.form.get("amount", "").strip()
    income_date_text = request.form.get("income_date", "").strip()
    note = request.form.get("note", "").strip()

    if not title:
        return None, "Please enter an income title."

    category = Category.query.filter_by(
        id=category_id,
        user_id=current_user.id,
        category_type="income"
    ).first()

    if not category:
        return None, "Please select a valid income category."

    try:
        amount = Decimal(amount_text)

        if not amount.is_finite() or amount <= 0:
            raise InvalidOperation

        amount = amount.quantize(Decimal("0.01"))

    except (InvalidOperation, ValueError):
        return None, "Please enter a valid amount greater than zero."

    try:
        income_date = date.fromisoformat(income_date_text)
    except ValueError:
        return None, "Please enter a valid income date."

    return {
        "title": title,
        "category": category,
        "amount": amount,
        "income_date": income_date,
        "note": note if note else None
    }, None


@income_bp.route("/")
@login_required
def index():

    incomes = (
        Income.query
        .filter_by(user_id=current_user.id)
        .order_by(Income.income_date.desc(), Income.id.desc())
        .all()
    )

    return render_template(
        "income/index.html",
        incomes=incomes
    )


@income_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():

    categories = get_income_categories()

    if request.method == "POST":

        data, error = validate_income_form()

        if error:
            flash(error, "danger")
            return render_template(
                "income/add.html",
                categories=categories
            )

        income = Income(
            user_id=current_user.id,
            category_id=data["category"].id,
            title=data["title"],
            amount=data["amount"],
            income_date=data["income_date"],
            note=data["note"]
        )

        try:
            db.session.add(income)
            db.session.commit()

            flash("Income added successfully!", "success")
            return redirect(url_for("income.index"))

        except Exception:
            db.session.rollback()
            flash("Could not save income. Please try again.", "danger")

    return render_template(
        "income/add.html",
        categories=categories
    )


@income_bp.route("/<int:income_id>/edit", methods=["GET", "POST"])
@login_required
def edit(income_id):

    # Only find an income record belonging to the logged-in user.
    income = Income.query.filter_by(
        id=income_id,
        user_id=current_user.id
    ).first_or_404()

    categories = get_income_categories()

    if request.method == "POST":

        data, error = validate_income_form()

        if error:
            flash(error, "danger")
            return render_template(
                "income/add.html",
                categories=categories,
                income=income,
                page_title="Edit Income",
                submit_label="Update Income"
            )

        income.title = data["title"]
        income.category_id = data["category"].id
        income.amount = data["amount"]
        income.income_date = data["income_date"]
        income.note = data["note"]

        try:
            db.session.commit()

            flash("Income updated successfully!", "success")
            return redirect(url_for("income.index"))

        except Exception:
            db.session.rollback()
            flash("Could not update income. Please try again.", "danger")

    return render_template(
        "income/add.html",
        categories=categories,
        income=income,
        page_title="Edit Income",
        submit_label="Update Income"
    )


@income_bp.route("/<int:income_id>/delete", methods=["POST"])
@login_required
def delete(income_id):

    # Only delete an income record belonging to the logged-in user.
    income = Income.query.filter_by(
        id=income_id,
        user_id=current_user.id
    ).first_or_404()

    try:
        db.session.delete(income)
        db.session.commit()

        flash("Income deleted successfully!", "success")

    except Exception:
        db.session.rollback()
        flash("Could not delete income. Please try again.", "danger")

    return redirect(url_for("income.index"))

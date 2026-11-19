
from datetime import date
from calendar import monthrange
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.routes import loans_bp
from app.models import (
    Loan,
    LoanInstallment,
    LoanPayment,
    LoanInterestAccrual
)


# --------------------------------------------------
# Helper: Add months safely to a date
# --------------------------------------------------
def add_months(original_date, months):

    month_index = original_date.month - 1 + months

    year = original_date.year + month_index // 12
    month = month_index % 12 + 1

    last_day = monthrange(year, month)[1]
    day = min(original_date.day, last_day)

    return date(year, month, day)


# --------------------------------------------------
# Helper: Generate four installment records
# --------------------------------------------------
def generate_installments(loan):

    principal = Decimal(str(loan.principal_amount))
    rate = Decimal(str(loan.monthly_interest_rate))

    installment_count = 4

    equal_principal = (
        principal / Decimal(installment_count)
    ).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP
    )

    outstanding_principal = principal

    for number in range(1, installment_count + 1):

        if number == installment_count:
            principal_due = outstanding_principal
        else:
            principal_due = equal_principal

        interest_due = (
            outstanding_principal * rate / Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP
        )

        due_date = add_months(
            loan.first_due_date,
            number - 1
        )

        db.session.add(
            LoanInstallment(
                loan_id=loan.id,
                installment_number=number,
                principal_due=principal_due,
                interest_due=interest_due,
                due_date=due_date,
                status="pending"
            )
        )

        outstanding_principal -= principal_due


# --------------------------------------------------
# Helper: Check whether financial terms are locked
# --------------------------------------------------
def loan_has_financial_history(loan):

    has_payments = (
        LoanPayment.query
        .filter_by(loan_id=loan.id)
        .first()
        is not None
    )

    has_interest_accruals = (
        LoanInterestAccrual.query
        .filter_by(loan_id=loan.id)
        .first()
        is not None
    )

    return has_payments or has_interest_accruals


# --------------------------------------------------
# Loan List
# --------------------------------------------------
@loans_bp.route("/")
@login_required
def index():

    loans = (
        Loan.query
        .filter_by(user_id=current_user.id)
        .order_by(Loan.loan_date.desc(), Loan.id.desc())
        .all()
    )

    return render_template(
        "loans/index.html",
        loans=loans
    )


# --------------------------------------------------
# Installment Schedule
# --------------------------------------------------
@loans_bp.route("/<int:loan_id>/schedule")
@login_required
def schedule(loan_id):

    loan = Loan.query.filter_by(
        id=loan_id,
        user_id=current_user.id
    ).first_or_404()

    installments = (
        LoanInstallment.query
        .filter_by(loan_id=loan.id)
        .order_by(LoanInstallment.installment_number)
        .all()
    )

    total_principal = sum(
        (item.principal_due for item in installments),
        Decimal("0.00")
    )

    total_interest = sum(
        (item.interest_due for item in installments),
        Decimal("0.00")
    )

    total_due = total_principal + total_interest

    return render_template(
        "loans/schedule.html",
        loan=loan,
        installments=installments,
        total_principal=total_principal,
        total_interest=total_interest,
        total_due=total_due
    )


# --------------------------------------------------
# Add Loan
# --------------------------------------------------
@loans_bp.route("/add", methods=["GET", "POST"])
@login_required
def add():

    if request.method == "POST":

        loan_type = request.form.get("loan_type", "").strip()
        direction = request.form.get("direction", "").strip()
        counterparty = request.form.get("counterparty", "").strip()
        repayment_method = request.form.get(
            "repayment_method", ""
        ).strip()
        note = request.form.get("note", "").strip()

        if loan_type not in ["personal", "bank", "finance"]:
            flash("Please select a valid loan type.", "danger")
            return redirect(url_for("loans.add"))

        if direction not in ["borrowed", "lent"]:
            flash("Please select a valid loan direction.", "danger")
            return redirect(url_for("loans.add"))

        if not counterparty:
            flash("Please enter the lender or borrower name.", "danger")
            return redirect(url_for("loans.add"))

        expected_method = (
            "flexible"
            if loan_type == "personal"
            else "four_installments"
        )

        if repayment_method != expected_method:
            flash("Invalid repayment method.", "danger")
            return redirect(url_for("loans.add"))

        try:
            principal_amount = Decimal(
                request.form.get("principal_amount", "").strip()
            )

            monthly_interest_rate = Decimal(
                request.form.get(
                    "monthly_interest_rate", ""
                ).strip()
            )

            if (
                not principal_amount.is_finite()
                or not monthly_interest_rate.is_finite()
            ):
                raise InvalidOperation

        except (InvalidOperation, ValueError):
            flash("Please enter valid financial amounts.", "danger")
            return redirect(url_for("loans.add"))

        if principal_amount <= 0:
            flash("Principal amount must be greater than zero.", "danger")
            return redirect(url_for("loans.add"))

        if monthly_interest_rate < 0:
            flash("Interest rate cannot be negative.", "danger")
            return redirect(url_for("loans.add"))

        try:
            loan_date = date.fromisoformat(
                request.form.get("loan_date", "").strip()
            )

            first_due_date_value = request.form.get(
                "first_due_date", ""
            ).strip()

            first_due_date = (
                date.fromisoformat(first_due_date_value)
                if first_due_date_value
                else None
            )

        except ValueError:
            flash("Please enter valid dates.", "danger")
            return redirect(url_for("loans.add"))

        if loan_type in ["bank", "finance"]:

            if not first_due_date:
                flash(
                    "Please select the first installment due date.",
                    "danger"
                )
                return redirect(url_for("loans.add"))

            if first_due_date < loan_date:
                flash(
                    "The first due date cannot be before the loan date.",
                    "danger"
                )
                return redirect(url_for("loans.add"))

        loan = Loan(
            user_id=current_user.id,
            loan_type=loan_type,
            direction=direction,
            counterparty=counterparty,
            principal_amount=principal_amount,
            monthly_interest_rate=monthly_interest_rate,
            repayment_method=repayment_method,
            loan_date=loan_date,
            first_due_date=first_due_date,
            installment_count=4,
            note=note,
            is_active=True
        )

        try:
            db.session.add(loan)
            db.session.flush()

            if loan_type in ["bank", "finance"]:
                generate_installments(loan)

            db.session.commit()

        except Exception:
            db.session.rollback()
            flash(
                "Unable to save the loan. Please check your information.",
                "danger"
            )
            return redirect(url_for("loans.add"))

        flash(
            "Loan and installment schedule saved successfully!",
            "success"
        )

        return redirect(url_for("loans.index"))

    return render_template("loans/add.html")


# --------------------------------------------------
# Edit Loan
# --------------------------------------------------
@loans_bp.route("/<int:loan_id>/edit", methods=["GET", "POST"])
@login_required
def edit(loan_id):

    loan = Loan.query.filter_by(
        id=loan_id,
        user_id=current_user.id
    ).first_or_404()

    terms_locked = loan_has_financial_history(loan)

    if request.method == "POST":

        counterparty = request.form.get(
            "counterparty", ""
        ).strip()

        note = request.form.get("note", "").strip()

        if not counterparty:
            flash(
                "Please enter the lender or borrower name.",
                "danger"
            )
            return redirect(
                url_for("loans.edit", loan_id=loan.id)
            )

        # These two fields are safe to update even when
        # payment or interest history already exists.
        loan.counterparty = counterparty
        loan.note = note

        if not terms_locked:

            loan_type = request.form.get(
                "loan_type", ""
            ).strip()

            direction = request.form.get(
                "direction", ""
            ).strip()

            repayment_method = request.form.get(
                "repayment_method", ""
            ).strip()

            if loan_type not in ["personal", "bank", "finance"]:
                flash("Please select a valid loan type.", "danger")
                return redirect(
                    url_for("loans.edit", loan_id=loan.id)
                )

            if direction not in ["borrowed", "lent"]:
                flash("Please select a valid loan direction.", "danger")
                return redirect(
                    url_for("loans.edit", loan_id=loan.id)
                )

            expected_method = (
                "flexible"
                if loan_type == "personal"
                else "four_installments"
            )

            if repayment_method != expected_method:
                flash("Invalid repayment method.", "danger")
                return redirect(
                    url_for("loans.edit", loan_id=loan.id)
                )

            try:
                principal_amount = Decimal(
                    request.form.get(
                        "principal_amount", ""
                    ).strip()
                )

                monthly_interest_rate = Decimal(
                    request.form.get(
                        "monthly_interest_rate", ""
                    ).strip()
                )

                if (
                    not principal_amount.is_finite()
                    or not monthly_interest_rate.is_finite()
                ):
                    raise InvalidOperation

            except (InvalidOperation, ValueError):
                flash(
                    "Please enter valid financial amounts.",
                    "danger"
                )
                return redirect(
                    url_for("loans.edit", loan_id=loan.id)
                )

            if principal_amount <= 0:
                flash(
                    "Principal amount must be greater than zero.",
                    "danger"
                )
                return redirect(
                    url_for("loans.edit", loan_id=loan.id)
                )

            if monthly_interest_rate < 0:
                flash(
                    "Interest rate cannot be negative.",
                    "danger"
                )
                return redirect(
                    url_for("loans.edit", loan_id=loan.id)
                )

            try:
                loan_date = date.fromisoformat(
                    request.form.get("loan_date", "").strip()
                )

                first_due_date_value = request.form.get(
                    "first_due_date", ""
                ).strip()

                first_due_date = (
                    date.fromisoformat(first_due_date_value)
                    if first_due_date_value
                    else None
                )

            except ValueError:
                flash("Please enter valid dates.", "danger")
                return redirect(
                    url_for("loans.edit", loan_id=loan.id)
                )

            if loan_type in ["bank", "finance"]:

                if not first_due_date:
                    flash(
                        "Please select the first installment due date.",
                        "danger"
                    )
                    return redirect(
                        url_for("loans.edit", loan_id=loan.id)
                    )

                if first_due_date < loan_date:
                    flash(
                        "The first due date cannot be before the loan date.",
                        "danger"
                    )
                    return redirect(
                        url_for("loans.edit", loan_id=loan.id)
                    )

            # Update the loan's financial details.
            loan.loan_type = loan_type
            loan.direction = direction
            loan.principal_amount = principal_amount
            loan.monthly_interest_rate = monthly_interest_rate
            loan.repayment_method = repayment_method
            loan.loan_date = loan_date
            loan.first_due_date = first_due_date
            loan.installment_count = 4

            # No payments or accruals exist, so the old
            # installment schedule can safely be regenerated.
            old_installments = LoanInstallment.query.filter_by(
                loan_id=loan.id
            ).all()

            for installment in old_installments:
                db.session.delete(installment)

            if loan_type in ["bank", "finance"]:
                db.session.flush()
                generate_installments(loan)

        try:
            db.session.commit()

        except Exception:
            db.session.rollback()
            flash(
                "Unable to update the loan. Please try again.",
                "danger"
            )
            return redirect(
                url_for("loans.edit", loan_id=loan.id)
            )

        flash("Loan updated successfully!", "success")
        return redirect(url_for("loans.index"))

    return render_template(
        "loans/edit.html",
        loan=loan,
        terms_locked=terms_locked
    )


# --------------------------------------------------
# Delete Loan
# --------------------------------------------------
@loans_bp.route("/<int:loan_id>/delete", methods=["POST"])
@login_required
def delete(loan_id):

    # Only allow users to delete their own loans.
    loan = Loan.query.filter_by(
        id=loan_id,
        user_id=current_user.id
    ).first_or_404()

    # Protect existing payment and interest history.
    if loan_has_financial_history(loan):

        flash(
            "This loan cannot be deleted because it has payment "
            "or interest history.",
            "danger"
        )

        return redirect(url_for("loans.index"))

    try:

        # Delete installment records first.
        installments = LoanInstallment.query.filter_by(
            loan_id=loan.id
        ).all()

        for installment in installments:
            db.session.delete(installment)

        # Delete the loan.
        db.session.delete(loan)

        db.session.commit()

        flash("Loan deleted successfully!", "success")

    except Exception:

        db.session.rollback()

        flash(
            "Unable to delete this loan. Please try again.",
            "danger"
        )

    return redirect(url_for("loans.index"))

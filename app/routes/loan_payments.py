
from datetime import date
from calendar import monthrange
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash
)
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Loan, LoanInstallment, LoanPayment, LoanInterestAccrual
from app.routes import loans_bp


CENT = Decimal("0.01")
ZERO = Decimal("0.00")


def money(value):
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


def add_months(original_date, months):
    month_index = original_date.month - 1 + months
    year = original_date.year + month_index // 12
    month = month_index % 12 + 1
    day = min(original_date.day, monthrange(year, month)[1])
    return date(year, month, day)


def get_paid_amounts(installment):
    payments = LoanPayment.query.filter_by(
        installment_id=installment.id
    ).all()

    principal_paid = sum(
        (Decimal(str(p.principal_paid)) for p in payments), ZERO
    )
    interest_paid = sum(
        (Decimal(str(p.interest_paid)) for p in payments), ZERO
    )

    return money(principal_paid), money(interest_paid)


def get_personal_loan_totals(loan):
    accruals = LoanInterestAccrual.query.filter_by(
        loan_id=loan.id
    ).all()

    payments = LoanPayment.query.filter_by(
        loan_id=loan.id
    ).all()

    total_interest = sum(
        (Decimal(str(a.interest_amount)) for a in accruals), ZERO
    )
    interest_paid = sum(
        (Decimal(str(p.interest_paid)) for p in payments), ZERO
    )
    principal_paid = sum(
        (Decimal(str(p.principal_paid)) for p in payments), ZERO
    )

    remaining_interest = max(ZERO, money(total_interest - interest_paid))
    remaining_principal = max(
        ZERO,
        money(Decimal(str(loan.principal_amount)) - principal_paid)
    )

    return remaining_interest, remaining_principal


def create_personal_interest_accruals(loan, payment_date):
    """
    Create one monthly interest accrual for each completed loan month.
    Each period is recorded only once.
    """

    month_number = 1

    while add_months(loan.loan_date, month_number) <= payment_date:

        period_start = add_months(loan.loan_date, month_number - 1)

        existing = LoanInterestAccrual.query.filter_by(
            loan_id=loan.id,
            period_start=period_start
        ).first()

        if existing:
            month_number += 1
            continue

        # Principal already repaid before this interest period began.
        previous_principal_paid = db.session.query(
            db.func.coalesce(db.func.sum(LoanPayment.principal_paid), 0)
        ).filter(
            LoanPayment.loan_id == loan.id,
            LoanPayment.payment_date < period_start
        ).scalar()

        outstanding_principal = money(
            Decimal(str(loan.principal_amount))
            - Decimal(str(previous_principal_paid or 0))
        )

        if outstanding_principal <= ZERO:
            month_number += 1
            continue

        rate = Decimal(str(loan.monthly_interest_rate))

        interest = money(
            outstanding_principal * rate / Decimal("100")
        )

        accrual = LoanInterestAccrual(
            loan_id=loan.id,
            period_start=period_start,
            principal_basis=outstanding_principal,
            interest_rate=rate,
            interest_amount=interest
        )

        db.session.add(accrual)
        month_number += 1


@loans_bp.route("/<int:loan_id>/payments")
@login_required
def payments(loan_id):

    loan = Loan.query.filter_by(
        id=loan_id,
        user_id=current_user.id
    ).first_or_404()

    payment_list = LoanPayment.query.filter_by(
        loan_id=loan.id
    ).order_by(
        LoanPayment.payment_date.desc(),
        LoanPayment.id.desc()
    ).all()

    total_principal_paid = sum(
        (Decimal(str(p.principal_paid)) for p in payment_list), ZERO
    )
    total_interest_paid = sum(
        (Decimal(str(p.interest_paid)) for p in payment_list), ZERO
    )

    return render_template(
        "loans/payments.html",
        loan=loan,
        payments=payment_list,
        total_principal_paid=money(total_principal_paid),
        total_interest_paid=money(total_interest_paid)
    )


@loans_bp.route("/<int:loan_id>/payments/add", methods=["GET", "POST"])
@login_required
def add_payment(loan_id):

    loan = Loan.query.filter_by(
        id=loan_id,
        user_id=current_user.id
    ).first_or_404()

    if not loan.is_active:
        flash("This loan is already completed.", "warning")
        return redirect(url_for("loans.payments", loan_id=loan.id))

    installment_options = []

    if loan.repayment_method == "four_installments":

        installments = LoanInstallment.query.filter_by(
            loan_id=loan.id
        ).order_by(
            LoanInstallment.installment_number
        ).all()

        for installment in installments:

            principal_paid, interest_paid = get_paid_amounts(installment)

            remaining_principal = max(
                ZERO,
                money(Decimal(str(installment.principal_due)) - principal_paid)
            )

            remaining_interest = max(
                ZERO,
                money(Decimal(str(installment.interest_due)) - interest_paid)
            )

            remaining_total = money(
                remaining_principal + remaining_interest
            )

            if remaining_total > ZERO:
                installment_options.append({
                    "installment": installment,
                    "remaining_principal": remaining_principal,
                    "remaining_interest": remaining_interest,
                    "remaining_total": remaining_total
                })

    if request.method == "POST":

        try:
            amount = money(request.form.get("amount", "0"))

            payment_date = date.fromisoformat(
                request.form.get("payment_date", "")
            )

            note = request.form.get("note", "").strip()

            if amount <= ZERO:
                raise ValueError("Payment amount must be greater than zero.")

            if payment_date < loan.loan_date:
                raise ValueError("Payment date cannot be before the loan date.")

            principal_paid = ZERO
            interest_paid = ZERO
            installment = None

            if loan.repayment_method == "four_installments":

                installment_id = request.form.get("installment_id", type=int)

                if not installment_id:
                    raise ValueError("Please select an installment.")

                installment = LoanInstallment.query.filter_by(
                    id=installment_id,
                    loan_id=loan.id
                ).first()

                if not installment:
                    raise ValueError("Invalid installment selected.")

                remaining_principal, remaining_interest = get_paid_amounts(
                    installment
                )

                remaining_principal = max(
                    ZERO,
                    money(
                        Decimal(str(installment.principal_due))
                        - remaining_principal
                    )
                )

                remaining_interest = max(
                    ZERO,
                    money(
                        Decimal(str(installment.interest_due))
                        - remaining_interest
                    )
                )

                remaining_total = money(
                    remaining_principal + remaining_interest
                )

                if amount > remaining_total:
                    raise ValueError(
                        f"Payment exceeds the remaining installment amount "
                        f"(¥{remaining_total:,.0f})."
                    )

                # Pay interest first, then principal.
                interest_paid = min(amount, remaining_interest)
                principal_paid = money(amount - interest_paid)

                new_principal_remaining = money(
                    remaining_principal - principal_paid
                )
                new_interest_remaining = money(
                    remaining_interest - interest_paid
                )

                if (
                    new_principal_remaining == ZERO
                    and new_interest_remaining == ZERO
                ):
                    installment.status = "paid"
                else:
                    installment.status = "partial"

            else:
                # Personal flexible loan.
                create_personal_interest_accruals(loan, payment_date)

                remaining_interest, remaining_principal = (
                    get_personal_loan_totals(loan)
                )

                remaining_total = money(
                    remaining_interest + remaining_principal
                )

                if amount > remaining_total:
                    raise ValueError(
                        f"Payment exceeds the remaining loan amount "
                        f"(¥{remaining_total:,.0f})."
                    )

                # Pay accrued interest first, then principal.
                interest_paid = min(amount, remaining_interest)
                principal_paid = money(amount - interest_paid)

            payment = LoanPayment(
                loan_id=loan.id,
                installment_id=installment.id if installment else None,
                principal_paid=principal_paid,
                interest_paid=interest_paid,
                payment_date=payment_date,
                note=note
            )

            db.session.add(payment)
            db.session.flush()

            # Mark the loan inactive when all principal and interest
            # have been paid.
            if loan.repayment_method == "four_installments":

                unpaid_installments = LoanInstallment.query.filter(
                    LoanInstallment.loan_id == loan.id,
                    LoanInstallment.status != "paid"
                ).count()

                if unpaid_installments == 0:
                    loan.is_active = False

            else:
                remaining_interest, remaining_principal = (
                    get_personal_loan_totals(loan)
                )

                if (
                    remaining_interest == ZERO
                    and remaining_principal == ZERO
                ):
                    loan.is_active = False

            db.session.commit()

            flash("Loan payment recorded successfully.", "success")

            return redirect(
                url_for("loans.payments", loan_id=loan.id)
            )

        except (ValueError, InvalidOperation) as error:
            db.session.rollback()
            flash(str(error), "danger")

        except Exception:
            db.session.rollback()
            flash(
                "Something went wrong while recording the payment.",
                "danger"
            )

    return render_template(
        "loans/add_payment.html",
        loan=loan,
        installment_options=installment_options,
        today=date.today()
    )

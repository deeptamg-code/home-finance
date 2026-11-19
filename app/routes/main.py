
from datetime import date
from decimal import Decimal

from flask import render_template
from flask_login import login_required, current_user
from sqlalchemy import func

from app.routes import main_bp
from app.extensions import db
from app.models import (
    Income,
    Expense,
    Loan,
    LoanPayment,
    SavingsGoal,
    SavingsTransaction,
)


@main_bp.route("/")
@login_required
def dashboard():

    today = date.today()
    month_start = today.replace(day=1)
    user_id = current_user.id

    # Helper: return total amount, or zero if there are no records.
    def get_total(query):
        return query.scalar() or 0

    # ----------------------------------
    # 1. Income
    # ----------------------------------
    total_income = get_total(
        db.session.query(func.coalesce(func.sum(Income.amount), 0))
        .filter(
            Income.user_id == user_id,
            Income.income_date <= today
        )
    )

    monthly_income = get_total(
        db.session.query(func.coalesce(func.sum(Income.amount), 0))
        .filter(
            Income.user_id == user_id,
            Income.income_date >= month_start,
            Income.income_date <= today
        )
    )

    # ----------------------------------
    # 2. Expenses
    # ----------------------------------
    total_expenses = get_total(
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(
            Expense.user_id == user_id,
            Expense.expense_date <= today
        )
    )

    monthly_expenses = get_total(
        db.session.query(func.coalesce(func.sum(Expense.amount), 0))
        .filter(
            Expense.user_id == user_id,
            Expense.expense_date >= month_start,
            Expense.expense_date <= today
        )
    )

    monthly_savings_allocation = max(
        Decimal("0"),
        Decimal(str(monthly_income or 0))
        - Decimal(str(monthly_expenses or 0))
    )

    # ----------------------------------
    # 3. Borrowed and lent loan amounts
    # ----------------------------------
    borrowed_total = get_total(
        db.session.query(func.coalesce(func.sum(Loan.principal_amount), 0))
        .filter(
            Loan.user_id == user_id,
            Loan.direction == "borrowed",
            Loan.loan_date <= today
        )
    )

    lent_total = get_total(
        db.session.query(func.coalesce(func.sum(Loan.principal_amount), 0))
        .filter(
            Loan.user_id == user_id,
            Loan.direction == "lent",
            Loan.loan_date <= today
        )
    )

    # ----------------------------------
    # 4. Actual loan payments
    # ----------------------------------
    borrowed_payments = get_total(
        db.session.query(
            func.coalesce(
                func.sum(
                    LoanPayment.principal_paid +
                    LoanPayment.interest_paid
                ), 0
            )
        )
        .join(Loan, LoanPayment.loan_id == Loan.id)
        .filter(
            Loan.user_id == user_id,
            Loan.direction == "borrowed",
            LoanPayment.payment_date <= today
        )
    )

    borrowed_principal_paid = get_total(
        db.session.query(
            func.coalesce(func.sum(LoanPayment.principal_paid), 0)
        )
        .join(Loan, LoanPayment.loan_id == Loan.id)
        .filter(
            Loan.user_id == user_id,
            Loan.direction == "borrowed",
            LoanPayment.payment_date <= today
        )
    )

    lent_collections = get_total(
        db.session.query(
            func.coalesce(
                func.sum(
                    LoanPayment.principal_paid +
                    LoanPayment.interest_paid
                ), 0
            )
        )
        .join(Loan, LoanPayment.loan_id == Loan.id)
        .filter(
            Loan.user_id == user_id,
            Loan.direction == "lent",
            LoanPayment.payment_date <= today
        )
    )

    # ----------------------------------
    # 5. Savings
    # ----------------------------------
    savings_opening = get_total(
        db.session.query(
            func.coalesce(func.sum(SavingsGoal.opening_balance), 0)
        )
        .filter(SavingsGoal.user_id == user_id)
    )
    activity_totals = (
        db.session.query(
            SavingsTransaction.transaction_type,
            func.coalesce(func.sum(SavingsTransaction.amount), 0)
        )
        .filter(
            SavingsTransaction.user_id == user_id,
            SavingsTransaction.transaction_date <= today
        )
        .group_by(SavingsTransaction.transaction_type)
        .all()
    )
    activity_totals = {
        transaction_type: Decimal(str(amount))
        for transaction_type, amount in activity_totals
    }
    savings_deposits = activity_totals.get("deposit", Decimal("0"))
    savings_withdrawals = activity_totals.get("withdrawal", Decimal("0"))
    all_savings = (
        savings_opening + savings_deposits
        - savings_withdrawals
    )

    # ----------------------------------
    # 6. Opening cash balance
    # ----------------------------------
    opening_cash = (
        current_user.financial_settings.opening_cash_balance
    )

    # ----------------------------------
    # 7. Calculate cash balance
    # ----------------------------------
    cash_balance = (
        opening_cash
        + total_income
        + borrowed_total
        + lent_collections
        - total_expenses
        - lent_total
        - borrowed_payments
        - savings_deposits
        + savings_withdrawals
    )

    # ----------------------------------
    # 8. Total available wealth
    # ----------------------------------
    total_available_wealth = cash_balance + all_savings
    outstanding_borrowed_loans = max(
        0,
        borrowed_total - borrowed_principal_paid
    )
    cashflow_scale = max(
        monthly_income,
        monthly_expenses,
        monthly_savings_allocation,
        1
    )

    # ----------------------------------
    # 9. Display dashboard
    # ----------------------------------
    return render_template(
        "dashboard/index.html",
        user=current_user,
        cash_balance=f"¥{cash_balance:,.0f}",
        monthly_income=f"¥{monthly_income:,.0f}",
        total_available_wealth=f"¥{total_available_wealth:,.0f}",
        monthly_expenses=f"¥{monthly_expenses:,.0f}",
        outstanding_borrowed_loans=f"¥{outstanding_borrowed_loans:,.0f}",
        monthly_income_amount=monthly_income,
        monthly_expenses_amount=monthly_expenses,
        monthly_savings_allocation=monthly_savings_allocation,
        savings_allocation_display=f"¥{monthly_savings_allocation:,.0f}",
        cashflow_scale=cashflow_scale
    )

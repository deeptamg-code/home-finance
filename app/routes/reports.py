from io import BytesIO
from flask import send_file

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    LongTable
)

from xml.sax.saxutils import escape


import csv
from io import StringIO, BytesIO
from flask import send_file

from datetime import date, datetime
from decimal import Decimal
from collections import defaultdict

from flask import render_template, request
from flask_login import login_required, current_user

from app.extensions import db
from app.routes import reports_bp
from app.models import (
    Income,
    Expense,
    Loan,
    LoanPayment,
    SavingsTransaction
)


ZERO = Decimal("0.00")


def csv_amount(value):
    return int(Decimal(str(value)).quantize(Decimal("1")))


def sum_amount(items, field_name):
    return sum(
        (getattr(item, field_name) or ZERO for item in items),
        ZERO
    )


def format_month_range(selected_month):
    month_start = date(
        selected_month.year,
        selected_month.month,
        1
    )

    if selected_month.month == 12:
        next_month = date(selected_month.year + 1, 1, 1)
    else:
        next_month = date(
            selected_month.year,
            selected_month.month + 1,
            1
        )

    return month_start, next_month


@reports_bp.route("/")
@login_required
def index():

    # Read selected month from URL.
    month_text = request.args.get(
        "month",
        date.today().strftime("%Y-%m")
    )

    # Validate selected month.
    try:
        selected_month = datetime.strptime(
            month_text,
            "%Y-%m"
        ).date()

    except ValueError:
        selected_month = date.today().replace(day=1)

    month_start, next_month = format_month_range(
        selected_month
    )

    # ----------------------------------------
    # Income
    # ----------------------------------------

    incomes = Income.query.filter(
        Income.user_id == current_user.id,
        Income.income_date >= month_start,
        Income.income_date < next_month
    ).all()

    total_income = sum_amount(incomes, "amount")

    income_categories = defaultdict(lambda: ZERO)

    for income in incomes:
        category_name = (
            income.category.name
            if income.category
            else "Uncategorized"
        )

        income_categories[category_name] += income.amount

    income_breakdown = sorted(
        income_categories.items(),
        key=lambda item: item[1],
        reverse=True
    )

    # ----------------------------------------
    # Expenses
    # ----------------------------------------

    expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.expense_date >= month_start,
        Expense.expense_date < next_month
    ).all()

    total_expenses = sum_amount(expenses, "amount")

    expense_categories = defaultdict(lambda: ZERO)

    for expense in expenses:
        category_name = (
            expense.category.name
            if expense.category
            else "Uncategorized"
        )

        expense_categories[category_name] += expense.amount

    expense_breakdown = sorted(
        expense_categories.items(),
        key=lambda item: item[1],
        reverse=True
    )

    # ----------------------------------------
    # Loans created during selected month
    # ----------------------------------------

    loans = Loan.query.filter(
        Loan.user_id == current_user.id,
        Loan.loan_date >= month_start,
        Loan.loan_date < next_month
    ).all()

    borrowed_total = sum(
        (
            loan.principal_amount
            for loan in loans
            if loan.direction == "borrowed"
        ),
        ZERO
    )

    lent_total = sum(
        (
            loan.principal_amount
            for loan in loans
            if loan.direction == "lent"
        ),
        ZERO
    )

    # ----------------------------------------
    # Actual loan payments during selected month
    # ----------------------------------------

    payments = (
        LoanPayment.query
        .join(Loan, LoanPayment.loan_id == Loan.id)
        .filter(
            Loan.user_id == current_user.id,
            LoanPayment.payment_date >= month_start,
            LoanPayment.payment_date < next_month
        )
        .all()
    )

    borrowed_repayments = ZERO
    lent_collections = ZERO

    for payment in payments:

        payment_total = (
            payment.principal_paid or ZERO
        ) + (
            payment.interest_paid or ZERO
        )

        if payment.loan.direction == "borrowed":
            borrowed_repayments += payment_total

        elif payment.loan.direction == "lent":
            lent_collections += payment_total

    # ----------------------------------------
    # Savings transactions
    # ----------------------------------------

    savings_transactions = SavingsTransaction.query.filter(
        SavingsTransaction.user_id == current_user.id,
        SavingsTransaction.transaction_date >= month_start,
        SavingsTransaction.transaction_date < next_month
    ).all()

    savings_deposits = ZERO
    savings_withdrawals = ZERO

    for transaction in savings_transactions:

        if transaction.transaction_type == "deposit":
            savings_deposits += transaction.amount

        elif transaction.transaction_type == "withdrawal":
            savings_withdrawals += transaction.amount

    # ----------------------------------------
    # Monthly cash movement
    # ----------------------------------------

    total_cash_in = (
        total_income
        + borrowed_total
        + lent_collections
        + savings_withdrawals
    )

    total_cash_out = (
        total_expenses
        + lent_total
        + borrowed_repayments
        + savings_deposits
    )

    net_cash_movement = total_cash_in - total_cash_out

    return render_template(
        "reports/index.html",

        selected_month=selected_month.strftime("%Y-%m"),

        total_income=total_income,
        total_expenses=total_expenses,

        income_breakdown=income_breakdown,
        expense_breakdown=expense_breakdown,

        borrowed_total=borrowed_total,
        lent_total=lent_total,

        borrowed_repayments=borrowed_repayments,
        lent_collections=lent_collections,

        savings_deposits=savings_deposits,
        savings_withdrawals=savings_withdrawals,

        total_cash_in=total_cash_in,
        total_cash_out=total_cash_out,
        net_cash_movement=net_cash_movement
    )


# --------------------------------------------------
# Export Financial Report to CSV
# --------------------------------------------------
@reports_bp.route("/export-csv")
@login_required
def export_csv():

    # Get selected month from URL.
    month_text = request.args.get(
        "month",
        date.today().strftime("%Y-%m")
    )

    # Validate selected month.
    try:
        selected_month = datetime.strptime(
            month_text,
            "%Y-%m"
        ).date()

    except ValueError:
        selected_month = date.today().replace(day=1)
        month_text = selected_month.strftime("%Y-%m")

    month_start, next_month = format_month_range(
        selected_month
    )

    # Create CSV in memory.
    output = StringIO()
    writer = csv.writer(output)

    # CSV title and headers.
    writer.writerow(["HOME FINANCE - MONTHLY REPORT"])
    writer.writerow(["Selected Month", month_text])
    writer.writerow([])

    writer.writerow([
        "Type",
        "Date",
        "Category / Type",
        "Description",
        "Amount In (JPY)",
        "Amount Out (JPY)"
    ])

    # ----------------------------------------
    # Income records
    # ----------------------------------------

    incomes = Income.query.filter(
        Income.user_id == current_user.id,
        Income.income_date >= month_start,
        Income.income_date < next_month
    ).all()

    total_income = ZERO

    for item in incomes:
        total_income += item.amount

        writer.writerow([
            "Income",
            item.income_date,
            item.category.name if item.category else "Uncategorized",
            item.title,
            csv_amount(item.amount),
            0
        ])

    # ----------------------------------------
    # Expense records
    # ----------------------------------------

    expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.expense_date >= month_start,
        Expense.expense_date < next_month
    ).all()

    total_expenses = ZERO

    for item in expenses:
        total_expenses += item.amount

        writer.writerow([
            "Expense",
            item.expense_date,
            item.category.name if item.category else "Uncategorized",
            item.title,
            0,
            csv_amount(item.amount)
        ])

    # ----------------------------------------
    # Loans created during selected month
    # ----------------------------------------

    loans = Loan.query.filter(
        Loan.user_id == current_user.id,
        Loan.loan_date >= month_start,
        Loan.loan_date < next_month
    ).all()

    borrowed_total = ZERO
    lent_total = ZERO

    for loan in loans:

        if loan.direction == "borrowed":
            borrowed_total += loan.principal_amount

        elif loan.direction == "lent":
            lent_total += loan.principal_amount

        writer.writerow([
            "Loan - " + loan.direction.title(),
            loan.loan_date,
            loan.loan_type.title(),
            loan.counterparty or "",
            csv_amount(loan.principal_amount) if loan.direction == "borrowed" else 0,
            csv_amount(loan.principal_amount) if loan.direction == "lent" else 0
        ])

    # ----------------------------------------
    # Actual loan payments
    # ----------------------------------------

    payments = (
        LoanPayment.query
        .join(Loan, LoanPayment.loan_id == Loan.id)
        .filter(
            Loan.user_id == current_user.id,
            LoanPayment.payment_date >= month_start,
            LoanPayment.payment_date < next_month
        )
        .all()
    )

    borrowed_repayments = ZERO
    lent_collections = ZERO

    for payment in payments:

        principal = payment.principal_paid or ZERO
        interest = payment.interest_paid or ZERO
        payment_total = principal + interest

        direction = payment.loan.direction

        if direction == "borrowed":
            borrowed_repayments += payment_total
        else:
            lent_collections += payment_total

        writer.writerow([
            "Loan Payment - " + direction.title(),
            payment.payment_date,
            payment.loan.loan_type.title(),
            payment.loan.counterparty or "",
            csv_amount(payment_total) if direction == "lent" else 0,
            csv_amount(payment_total) if direction == "borrowed" else 0
        ])

    # ----------------------------------------
    # Savings transactions
    # ----------------------------------------

    savings_transactions = SavingsTransaction.query.filter(
        SavingsTransaction.user_id == current_user.id,
        SavingsTransaction.transaction_date >= month_start,
        SavingsTransaction.transaction_date < next_month
    ).all()

    savings_deposits = ZERO
    savings_withdrawals = ZERO

    for transaction in savings_transactions:

        if transaction.transaction_type == "deposit":
            savings_deposits += transaction.amount

        else:
            savings_withdrawals += transaction.amount

        writer.writerow([
            "Savings - " + transaction.transaction_type.title(),
            transaction.transaction_date,
            transaction.goal.name,
            transaction.note or "",
            csv_amount(transaction.amount) if transaction.transaction_type == "withdrawal" else 0,
            csv_amount(transaction.amount) if transaction.transaction_type == "deposit" else 0
        ])

    # ----------------------------------------
    # Monthly summary
    # ----------------------------------------

    total_cash_in = (
        total_income
        + borrowed_total
        + lent_collections
        + savings_withdrawals
    )

    total_cash_out = (
        total_expenses
        + lent_total
        + borrowed_repayments
        + savings_deposits
    )

    net_cash_movement = total_cash_in - total_cash_out

    writer.writerow([
        "Total",
        "",
        "",
        "",
        csv_amount(total_cash_in),
        csv_amount(total_cash_out)
    ])
    writer.writerow([])
    writer.writerow(["MONTHLY SUMMARY"])
    writer.writerow(["Description", "Amount (JPY)"])
    writer.writerow(["Total Income", csv_amount(total_income)])
    writer.writerow(["Total Expenses", csv_amount(total_expenses)])
    writer.writerow(["Money Borrowed", csv_amount(borrowed_total)])
    writer.writerow(["Money Lent", csv_amount(lent_total)])
    writer.writerow(["Borrowed Loan Repayments", csv_amount(borrowed_repayments)])
    writer.writerow(["Collections from Lent Loans", csv_amount(lent_collections)])
    writer.writerow(["Savings Deposits", csv_amount(savings_deposits)])
    writer.writerow(["Savings Withdrawals", csv_amount(savings_withdrawals)])
    writer.writerow(["Total Cash In", csv_amount(total_cash_in)])
    writer.writerow(["Total Cash Out", csv_amount(total_cash_out)])
    writer.writerow(["Net Cash Movement", csv_amount(net_cash_movement)])

    # Convert to Excel-friendly UTF-8 CSV.
    csv_data = BytesIO(
        output.getvalue().encode("utf-8-sig")
    )

    output.close()
    csv_data.seek(0)

    return send_file(
        csv_data,
        mimetype="text/csv",
        as_attachment=True,
        download_name=f"financial_report_{month_text}.csv"
    )



# --------------------------------------------------
# Export Financial Report to PDF
# --------------------------------------------------
@reports_bp.route("/export-pdf")
@login_required
def export_pdf():

    # Get selected month.
    month_text = request.args.get(
        "month",
        date.today().strftime("%Y-%m")
    )

    # Validate selected month.
    try:
        selected_month = datetime.strptime(
            month_text,
            "%Y-%m"
        ).date()

    except ValueError:
        selected_month = date.today().replace(day=1)
        month_text = selected_month.strftime("%Y-%m")

    month_start, next_month = format_month_range(
        selected_month
    )

    # ----------------------------------------
    # Register Japanese-compatible PDF font
    # ----------------------------------------

    font_name = "HeiseiMin-W3"

    pdfmetrics.registerFont(
        UnicodeCIDFont(font_name)
    )

    # ----------------------------------------
    # Get income records
    # ----------------------------------------

    incomes = Income.query.filter(
        Income.user_id == current_user.id,
        Income.income_date >= month_start,
        Income.income_date < next_month
    ).all()

    total_income = sum_amount(incomes, "amount")

    # ----------------------------------------
    # Get expense records
    # ----------------------------------------

    expenses = Expense.query.filter(
        Expense.user_id == current_user.id,
        Expense.expense_date >= month_start,
        Expense.expense_date < next_month
    ).all()

    total_expenses = sum_amount(expenses, "amount")

    # ----------------------------------------
    # Get loans created during the month
    # ----------------------------------------

    loans = Loan.query.filter(
        Loan.user_id == current_user.id,
        Loan.loan_date >= month_start,
        Loan.loan_date < next_month
    ).all()

    borrowed_total = ZERO
    lent_total = ZERO

    # ----------------------------------------
    # Get actual loan payments
    # ----------------------------------------

    payments = (
        LoanPayment.query
        .join(Loan, LoanPayment.loan_id == Loan.id)
        .filter(
            Loan.user_id == current_user.id,
            LoanPayment.payment_date >= month_start,
            LoanPayment.payment_date < next_month
        )
        .all()
    )

    borrowed_repayments = ZERO
    lent_collections = ZERO

    for payment in payments:

        payment_total = (
            payment.principal_paid or ZERO
        ) + (
            payment.interest_paid or ZERO
        )

        if payment.loan.direction == "borrowed":
            borrowed_repayments += payment_total

        else:
            lent_collections += payment_total

    # ----------------------------------------
    # Get savings transactions
    # ----------------------------------------

    savings_transactions = SavingsTransaction.query.filter(
        SavingsTransaction.user_id == current_user.id,
        SavingsTransaction.transaction_date >= month_start,
        SavingsTransaction.transaction_date < next_month
    ).all()

    savings_deposits = ZERO
    savings_withdrawals = ZERO

    for transaction in savings_transactions:

        if transaction.transaction_type == "deposit":
            savings_deposits += transaction.amount

        else:
            savings_withdrawals += transaction.amount

    # ----------------------------------------
    # Calculate loan totals
    # ----------------------------------------

    for loan in loans:

        if loan.direction == "borrowed":
            borrowed_total += loan.principal_amount

        else:
            lent_total += loan.principal_amount

    # ----------------------------------------
    # Calculate cash movement
    # ----------------------------------------

    total_cash_in = (
        total_income
        + borrowed_total
        + lent_collections
        + savings_withdrawals
    )

    total_cash_out = (
        total_expenses
        + lent_total
        + borrowed_repayments
        + savings_deposits
    )

    net_cash_movement = total_cash_in - total_cash_out

    # ----------------------------------------
    # Create PDF in memory
    # ----------------------------------------

    pdf_buffer = BytesIO()

    document = SimpleDocTemplate(
        pdf_buffer,
        pagesize=A4,
        rightMargin=35,
        leftMargin=35,
        topMargin=35,
        bottomMargin=35
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "ReportTitle",
        parent=styles["Title"],
        fontName=font_name,
        fontSize=20,
        leading=26,
        alignment=TA_CENTER,
        textColor=colors.HexColor("#172554")
    )

    heading_style = ParagraphStyle(
        "ReportHeading",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=13,
        leading=18,
        textColor=colors.HexColor("#172554"),
        spaceBefore=12,
        spaceAfter=8
    )

    normal_style = ParagraphStyle(
        "ReportNormal",
        parent=styles["Normal"],
        fontName=font_name,
        fontSize=9,
        leading=13
    )

    small_style = ParagraphStyle(
        "ReportSmall",
        parent=normal_style,
        fontSize=7,
        leading=9
    )

    story = []

    # ----------------------------------------
    # Report title
    # ----------------------------------------

    story.append(
        Paragraph("HOME FINANCE", title_style)
    )

    story.append(
        Paragraph(
            f"Financial Report - {escape(month_text)}",
            normal_style
        )
    )

    story.append(Spacer(1, 18))

    # ----------------------------------------
    # Monthly summary
    # ----------------------------------------

    story.append(
        Paragraph("Monthly Summary", heading_style)
    )

    summary_data = [
        ["Description", "Amount (JPY)"],
        ["Total Income", f"¥{total_income:,.0f}"],
        ["Total Expenses", f"¥{total_expenses:,.0f}"],
        ["Money Borrowed", f"¥{borrowed_total:,.0f}"],
        ["Money Lent", f"¥{lent_total:,.0f}"],
        ["Borrowed Loan Repayments", f"¥{borrowed_repayments:,.0f}"],
        ["Collections from Lent Loans", f"¥{lent_collections:,.0f}"],
        ["Savings Deposits", f"¥{savings_deposits:,.0f}"],
        ["Savings Withdrawals", f"¥{savings_withdrawals:,.0f}"],
        ["Total Cash In", f"¥{total_cash_in:,.0f}"],
        ["Total Cash Out", f"¥{total_cash_out:,.0f}"],
        ["Net Cash Movement", f"¥{net_cash_movement:,.0f}"]
    ]

    summary_table = Table(
        summary_data,
        colWidths=[330, 180]
    )

    summary_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#172554")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("ALIGN", (1, 1), (1, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
            ("BACKGROUND", (0, -1), (-1, -1),
             colors.HexColor("#e8edf7")),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7)
        ])
    )

    story.append(summary_table)

    # ----------------------------------------
    # Transaction details
    # ----------------------------------------

    story.append(
        Paragraph("Transaction Details", heading_style)
    )

    detail_data = [
        [
            "Type",
            "Date",
            "Category / Type",
            "Description",
            "Amount In (JPY)",
            "Amount Out (JPY)"
        ]
    ]

    # Income details.
    for item in incomes:
        detail_data.append([
            Paragraph("Income", small_style),
            Paragraph(str(item.income_date), small_style),
            Paragraph(
                escape(item.category.name if item.category else "Uncategorized"),
                small_style
            ),
            Paragraph(escape(item.title or ""), small_style),
            Paragraph(f"¥{item.amount:,.0f}", small_style),
            Paragraph("¥0", small_style)
        ])

    # Expense details.
    for item in expenses:
        detail_data.append([
            Paragraph("Expense", small_style),
            Paragraph(str(item.expense_date), small_style),
            Paragraph(
                escape(item.category.name if item.category else "Uncategorized"),
                small_style
            ),
            Paragraph(escape(item.title or ""), small_style),
            Paragraph("¥0", small_style),
            Paragraph(f"¥{item.amount:,.0f}", small_style)
        ])

    # Loan details.
    for loan in loans:
        if loan.direction == "borrowed":
            detail_data.append([
                Paragraph("Borrowed", small_style),
                Paragraph(str(loan.loan_date), small_style),
                Paragraph(escape(loan.loan_type), small_style),
                Paragraph(escape(loan.counterparty or ""), small_style),
                Paragraph(f"¥{loan.principal_amount:,.0f}", small_style),
                Paragraph("¥0", small_style)
            ])
        else:
            detail_data.append([
                Paragraph("Lent", small_style),
                Paragraph(str(loan.loan_date), small_style),
                Paragraph(escape(loan.loan_type), small_style),
                Paragraph(escape(loan.counterparty or ""), small_style),
                Paragraph("¥0", small_style),
                Paragraph(f"¥{loan.principal_amount:,.0f}", small_style)
            ])

    # Actual payment details.
    for payment in payments:

        payment_total = (
            payment.principal_paid or ZERO
        ) + (
            payment.interest_paid or ZERO
        )

        detail_data.append([
            Paragraph(
                "Repayment" if payment.loan.direction == "borrowed"
                else "Collection",
                small_style
            ),
            Paragraph(str(payment.payment_date), small_style),
            Paragraph(escape(payment.loan.loan_type), small_style),
            Paragraph(escape(payment.loan.counterparty or ""), small_style),
            Paragraph(
                f"¥{payment_total:,.0f}" if payment.loan.direction == "lent" else "¥0",
                small_style
            ),
            Paragraph(
                f"¥{payment_total:,.0f}" if payment.loan.direction == "borrowed" else "¥0",
                small_style
            )
        ])

    # Savings details.
    for transaction in savings_transactions:
        detail_data.append([
            Paragraph(
                "Savings " + transaction.transaction_type.title(),
                small_style
            ),
            Paragraph(str(transaction.transaction_date), small_style),
            Paragraph(escape(transaction.goal.name), small_style),
            Paragraph(escape(transaction.note or ""), small_style),
            Paragraph(
                f"¥{transaction.amount:,.0f}" if transaction.transaction_type == "withdrawal" else "¥0",
                small_style
            ),
            Paragraph(
                f"¥{transaction.amount:,.0f}" if transaction.transaction_type == "deposit" else "¥0",
                small_style
            )
        ])

    if len(detail_data) == 1:
        detail_data.append([
            Paragraph("No transactions", small_style),
            "",
            "",
            "",
            "",
            ""
        ])

    detail_data.append([
        Paragraph("Total", small_style),
        "",
        "",
        "",
        Paragraph(f"¥{total_cash_in:,.0f}", small_style),
        Paragraph(f"¥{total_cash_out:,.0f}", small_style)
    ])

    details_table = LongTable(
        detail_data,
        colWidths=[65, 65, 100, 125, 82, 82],
        repeatRows=1
    )

    details_table.setStyle(
        TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("BACKGROUND", (0, 0), (-1, 0),
             colors.HexColor("#172554")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (4, 1), (5, -1), "RIGHT"),
            ("BACKGROUND", (0, -1), (-1, -1),
             colors.HexColor("#e8edf7")),
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor("#172554")),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6)
        ])
    )

    story.append(details_table)

    # ----------------------------------------
    # Build and return PDF
    # ----------------------------------------

    document.build(story)

    pdf_buffer.seek(0)

    return send_file(
        pdf_buffer,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"financial_report_{month_text}.pdf"
    )

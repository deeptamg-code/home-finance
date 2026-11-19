
from flask import Blueprint

auth_bp = Blueprint("auth", __name__)
main_bp = Blueprint("main", __name__)
income_bp = Blueprint("income", __name__)
expenses_bp = Blueprint("expenses", __name__)
savings_bp = Blueprint("savings", __name__)
loans_bp = Blueprint("loans", __name__)

# Financial Reports
reports_bp = Blueprint("reports", __name__)

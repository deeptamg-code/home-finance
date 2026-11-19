
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, current_user

from app.routes import auth_bp
from app.extensions import db
from app.models import User, FinancialSettings


# -----------------------------
# User Registration
# -----------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":

        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not username or not email or not password:
            flash("Please fill in all required fields.", "danger")
            return redirect(url_for("auth.register"))

        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return redirect(url_for("auth.register"))

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return redirect(url_for("auth.register"))

        existing_user = User.query.filter_by(email=email).first()

        if existing_user:
            flash("This email is already registered.", "danger")
            return redirect(url_for("auth.register"))

        try:
            user = User(
                username=username,
                email=email
            )

            user.set_password(password)

            db.session.add(user)
            db.session.flush()

            settings = FinancialSettings(
                user_id=user.id,
                currency="JPY",
                opening_cash_balance=0
            )

            db.session.add(settings)
            db.session.commit()

            flash("Registration successful! Please log in.", "success")

            return redirect(url_for("auth.login"))

        except Exception:
            db.session.rollback()
            flash("Registration failed. Please try again.", "danger")

    return render_template("auth/register.html")


# -----------------------------
# User Login
# -----------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and user.check_password(password):

            login_user(user)

            flash("Welcome back!", "success")

            return redirect(url_for("main.dashboard"))

        flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


# -----------------------------
# User Logout
# -----------------------------
@auth_bp.route("/logout", methods=["POST"])
def logout():

    if current_user.is_authenticated:
        logout_user()
        flash("You have been logged out.", "success")

    return redirect(url_for("auth.login"))


import os
from flask import Flask, send_from_directory

from config import Config
from app.extensions import db, migrate, login_manager, csrf


def create_app():

    app = Flask(__name__)

    # Load configuration
    app.config.from_object(Config)

    # Create instance directory
    os.makedirs(app.instance_path, exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Import models
    from app import models

    # Import blueprints
    from app.routes import (
        auth_bp,
        main_bp,
        income_bp,
        expenses_bp,
        savings_bp,
        loans_bp,
        reports_bp
    )

    # Import route modules
    from app.routes import auth
    from app.routes import main
    from app.routes import income
    from app.routes import expenses
    from app.routes import savings
    from app.routes import loans
    from app.routes import loan_payments
    from app.routes import reports

    # Register blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(income_bp, url_prefix="/income")
    app.register_blueprint(expenses_bp, url_prefix="/expenses")
    app.register_blueprint(savings_bp, url_prefix="/savings")
    app.register_blueprint(loans_bp, url_prefix="/loans")
    app.register_blueprint(reports_bp, url_prefix="/reports")

    # PWA: Serve the service worker from the website root.
    # This allows it to control the whole application.
    @app.route("/sw.js")
    def service_worker():
        response = send_from_directory(
            app.static_folder,
            "sw.js",
            mimetype="application/javascript"
        )
        response.headers["Service-Worker-Allowed"] = "/"
        response.headers["Cache-Control"] = "no-cache"
        return response

    return app


from app.models import User


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

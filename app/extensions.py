
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# Database connection
db = SQLAlchemy()

# Database migration
migrate = Migrate()

# Login management
login_manager = LoginManager()
login_manager.login_view = "auth.login"

# CSRF security
csrf = CSRFProtect()

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Database connection
db = SQLAlchemy()

# Database migration
migrate = Migrate()

# Login management
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.session_protection = "strong"

# CSRF security
csrf = CSRFProtect()

# Rate limiting for sensitive authentication endpoints.
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[]
)

from flask import Flask, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from app.config import Config

# -------------------------------
# extensiones globales
# -------------------------------
db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__, static_folder='app/static')
    app.config.from_object(Config)
    app.config['UPLOAD_FOLDER'] = 'app/static/uploads'
    # -------------------------------
    # inicialización de extensiones
    # -------------------------------
    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # -------------------------------
    # Importar modelos *después* de inicializar db
    # -------------------------------
    from app.models.models import Usuario

    # -------------------------------
    # función para cargar usuarios (Flask-Login)
    # -------------------------------
    @login_manager.user_loader
    def load_user(user_id):
        return Usuario.query.get(int(user_id))

    # -------------------------------
    # registro de blueprints
    # -------------------------------
    from app.controllers.controller import (
        inicio_cp, usuario_cp, producto_cp, admin_cp, auth_cp
    )

    app.register_blueprint(inicio_cp)
    app.register_blueprint(usuario_cp)
    app.register_blueprint(producto_cp)
    app.register_blueprint(admin_cp, url_prefix='/admin')
    app.register_blueprint(auth_cp)

    # -------------------------------
    # ruta principal
    # -------------------------------
    @app.route('/')
    def home():
        return redirect(url_for('inicio_cp.inicio_publico'))

    return app

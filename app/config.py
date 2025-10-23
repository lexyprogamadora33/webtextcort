import os
from dotenv import load_dotenv

# Carga las variables de entorno desde .env si existe
load_dotenv()

class Config:
    # Clave secreta para sesiones y seguridad
    SECRET_KEY = os.getenv('SECRET_KEY', 'clave-super-secreta')

    # URI de conexión a la base de datos MySQL (usando PyMySQL)
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URI")

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_SECURE = False  # Cambia a True si usas HTTPS

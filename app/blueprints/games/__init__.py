from flask import Blueprint

# Creates a generic games blueprint to future-proof the app
games_bp = Blueprint('games', __name__)

from . import routes
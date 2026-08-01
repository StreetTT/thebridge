"""Application factory.

``create_app`` builds the Flask app and registers blueprints. Future phone-to-Notion
projects add their own blueprints here without touching existing routes.
"""

from flask import Flask

from app.config import Config


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)

    from app.blueprints.health.routes import health_bp
    from app.blueprints.savings.routes import savings_bp
    from app.blueprints.transactions.routes import transactions_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(savings_bp)

    return app

"""PythonAnywhere WSGI entry point.

The web app's WSGI file should expose ``application``. On PythonAnywhere you can
either set ``NOTION_TOKEN`` / ``API_SECRET`` in the WSGI file before importing, or
rely on a ``.env`` file loaded by ``app.config``.
"""

from app import create_app

application = create_app()

if __name__ == "__main__":
    application.run(debug=True)

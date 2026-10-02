"""Servidor de desarrollo:  python run.py   (en producción se usa gunicorn, ver wsgi.py)"""
from app import create_app

if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5000, debug=False)

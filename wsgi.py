from gevent import monkey
monkey.patch_all()  # MUST be first

from app import create_app, socketio  # noqa: E402

app = create_app()

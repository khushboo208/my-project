from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200))
    provider = db.Column(db.String(50), default="local")
    live_location_enabled = db.Column(db.Boolean, default=False, nullable=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        if not self.password:
            return False

        return check_password_hash(self.password, password)


class SavedOutfit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
    )
    outfit_data = db.Column(db.Text, nullable=False)
    scheduled_date = db.Column(db.String(20))
    note = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


def ensure_user_columns():
    inspector = inspect(db.engine)
    columns = {column["name"] for column in inspector.get_columns("user")}
    if "live_location_enabled" not in columns:
        db.session.execute(
            text("ALTER TABLE user ADD COLUMN live_location_enabled BOOLEAN NOT NULL DEFAULT 0")
        )
        db.session.commit()
    if "is_admin" not in columns:
        db.session.execute(
            text("ALTER TABLE user ADD COLUMN is_admin BOOLEAN NOT NULL DEFAULT 0")
        )
        db.session.commit()

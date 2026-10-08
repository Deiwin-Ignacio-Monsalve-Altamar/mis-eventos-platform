import os


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://mis_eventos:mis_eventos_dev@localhost:5432/mis_eventos",
)


class Config:
    DATABASE_URL = DATABASE_URL
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

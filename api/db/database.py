import psycopg2

from data.utils.utils import DB_CONFIG


def get_connection():
    return psycopg2.connect(**DB_CONFIG)
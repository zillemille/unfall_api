import psycopg2

from data.const.constants import DB_CONFIG


def get_connection():
    return psycopg2.connect(**DB_CONFIG)
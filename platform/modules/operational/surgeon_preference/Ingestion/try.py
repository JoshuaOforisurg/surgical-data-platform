import psycopg2

psycopg2.connect(
    dbname="surgical_data_platform",
    user="joshuaofori",
    host="localhost",
    port=5432
)

import snowflake.connector

STUDENT_DEFAULT_PASSWORD = "student123"  # default password

# Snowflake connection parameters
SNOWFLAKE_ACCOUNT = 'gazzvap-iw54421'
SNOWFLAKE_USER = 'KAUSTUBH'
SNOWFLAKE_PASSWORD = 'Qwerty*123'
SNOWFLAKE_DATABASE = 'UNIVERSITYPLACEMENTPORTAL'
SNOWFLAKE_SCHEMA = 'PUBLIC'

# Initialize Snowflake connection
connection = None

def init_snowflake_connection():
    connection = snowflake.connector.connect(
        user=SNOWFLAKE_USER,
        password=SNOWFLAKE_PASSWORD,
        account=SNOWFLAKE_ACCOUNT,
        database=SNOWFLAKE_DATABASE,
        schema=SNOWFLAKE_SCHEMA
    )
    return connection
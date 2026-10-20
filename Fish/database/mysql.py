from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base


MYSQL_USER = "root"

MYSQL_PASSWORD = "w18639772751"

MYSQL_HOST = "localhost"

MYSQL_PORT = 3306

MYSQL_DATABASE = "yellow_eel_agent"



DATABASE_URL = (
    f"mysql+pymysql://"
    f"{MYSQL_USER}:"
    f"{MYSQL_PASSWORD}@"
    f"{MYSQL_HOST}:"
    f"{MYSQL_PORT}/"
    f"{MYSQL_DATABASE}"
    "?charset=utf8mb4"
)



engine = create_engine(

    DATABASE_URL,

    echo=False,

    pool_size=10,

    max_overflow=20,

    pool_pre_ping=True   # 自动检测连接是否失效

)



SessionLocal = sessionmaker(

    autocommit=False,

    autoflush=False,

    bind=engine

)



Base = declarative_base()



def get_db():

    """
    提供数据库Session

    Tool调用数据库时使用
    """

    db = SessionLocal()

    try:

        yield db

    finally:

        db.close()



def test_connection():

    """
    测试MySQL连接
    """

    try:

        with engine.connect():

            print("MySQL连接成功")

    except Exception as e:

        print("MySQL连接失败:",e)



if __name__=="__main__":

    test_connection()
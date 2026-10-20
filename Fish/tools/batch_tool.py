from langchain.tools import tool

from Fish.database.mysql import SessionLocal

from Fish.database.models import BatchInfo



@tool
def query_batch_info(batch_code:str):
    """
    查询生产批次信息。

    输入:
    batch_code:
        生产批次编号，例如 B2026001

    返回:
        批次基本信息，包括养殖池facility_id

    用于后续水质、投喂、告警查询。
    """


    # 创建数据库连接

    db = SessionLocal()


    try:


        # ORM查询

        batch = (
            db.query(BatchInfo)
            .filter(
                BatchInfo.batch_code == batch_code
            )
            .first()
        )


        # 没找到

        if batch is None:

            return {

                "status":"failed",

                "message":
                f"没有找到批次:{batch_code}"

            }



        # 返回给LLM的数据
        # 不直接返回ORM对象

        result = {

            "query_status": "success",

            "batch_code":
                batch.batch_code,

            "facility_id":
                batch.facility_id,

            "species":
                batch.species,

            "start_date":
                str(batch.start_date),

            "density":
                batch.density,

            "production_status":
                batch.status
        }

        return result



    finally:

        db.close()
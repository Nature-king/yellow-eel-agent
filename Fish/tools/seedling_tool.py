from langchain.tools import tool


from Fish.database.mysql import SessionLocal

from Fish.database.models import SeedlingQuality



@tool
def query_seedling_quality(batch_code: str):
    """
    查询指定生产批次的苗种质量信息。

    参数:
        batch_code:
            生产批次编号

    返回:
        初始重量
        成活率
        健康评分

    用于分析养殖异常原因。
    """

    # 创建数据库Session

    db = SessionLocal()


    try:

        # 查询对应批次苗种数据

        seedling = (
            db.query(
                SeedlingQuality
            )
            .filter(
                SeedlingQuality.batch_code == batch_code
            )
            .first()
        )


        # 没有数据

        if seedling is None:

            return {

                "status":"failed",

                "message":
                f"没有找到批次 {batch_code} 的苗种信息"

            }


        # 返回给Agent的结构化数据

        result = {


            "status":"success",


            "batch_code":
                seedling.batch_code,


            "initial_weight":
                seedling.initial_weight,


            "survival_rate":
                seedling.survival_rate,


            "health_score":
                seedling.health_score

        }


        return result



    finally:

        db.close()
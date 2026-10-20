from langchain.tools import tool


from Fish.database.mysql import SessionLocal

from Fish.database.models import WaterQuality



@tool
def query_water_quality(facility_id: str):
    """
    查询指定养殖池的水质监测数据。

    参数:
        facility_id:
            养殖池编号，例如 A001

    返回:
        最新水质数据
        最近水质变化趋势

    用于判断:
        水温
        pH
        溶氧
        氨氮
        是否异常
    """

    db = SessionLocal()


    try:

        # ==========================
        # 查询最近10条水质记录
        # ==========================

        records = (

            db.query(
                WaterQuality
            )

            .filter(
                WaterQuality.facility_id == facility_id
            )

            .order_by(
                WaterQuality.record_time.desc()
            )

            .limit(10)

            .all()

        )


        # 没有数据

        if not records:

            return {

                "status":"failed",

                "message":
                f"没有找到{facility_id}水质数据"

            }



        # ==========================
        # 最新一条数据
        # ==========================

        latest = records[0]


        latest_data = {


            "temperature":
                latest.temperature,


            "ph":
                latest.ph,


            "oxygen":
                latest.oxygen,


            "ammonia":
                latest.ammonia,


            "time":
                str(latest.record_time)

        }



        # ==========================
        # 历史趋势
        # ==========================

        trend = []


        for item in reversed(records):


            trend.append(

                {

                "time":
                    str(item.record_time),


                "oxygen":
                    item.oxygen,


                "temperature":
                    item.temperature

                }

            )



        return {


            "status":
                "success",


            "facility_id":
                facility_id,


            "latest":
                latest_data,


            "trend":
                trend

        }



    finally:

        db.close()
from langchain.tools import tool


from Fish.database.mysql import SessionLocal

from Fish.database.models import FeedingRecord



@tool
def query_feeding_record(facility_id: str):
    """
    查询指定养殖池投喂和摄食情况。

    参数:
        facility_id:
            养殖池编号，例如 A001

    返回:
        最新投喂数据
        最近摄食趋势

    用于分析:
        摄食下降
        投喂异常
        生长异常原因
    """


    db = SessionLocal()


    try:


        # ==========================
        # 查询最近10次投喂记录
        # ==========================

        records = (

            db.query(
                FeedingRecord
            )

            .filter(
                FeedingRecord.facility_id == facility_id
            )

            .order_by(

                FeedingRecord.record_time.desc()

            )

            .limit(10)

            .all()

        )


        if not records:


            return {


                "status":
                    "failed",


                "message":
                    f"没有找到{facility_id}投喂数据"

            }



        # ==========================
        # 最新记录
        # ==========================


        latest = records[0]


        latest_data = {


            "feed_amount":

                latest.feed_amount,


            "eat_rate":

                latest.eat_rate,


            "time":

                str(latest.record_time)

        }



        # ==========================
        # 摄食趋势
        # ==========================

        trend=[]


        for item in reversed(records):


            trend.append(

                {


                "time":
                    str(item.record_time),


                "feed_amount":
                    item.feed_amount,


                "eat_rate":
                    item.eat_rate


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
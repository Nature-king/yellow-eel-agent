"""
初始化黄鳝智慧养殖模拟数据

运行:
python -m Fish.database.init_data

功能:
1. 清空旧数据
2. 创建批次
3. 创建苗种数据
4. 创建水质数据
5. 创建投喂数据
6. 创建报警数据
7. 创建设备状态
"""


from datetime import datetime, timedelta
import random


from Fish.database.mysql import SessionLocal

from Fish.database.models import (
    BatchInfo,
    SeedlingQuality,
    WaterQuality,
    FeedingRecord,
    AlarmRecord,
    DeviceStatus
)



# ===============================
# 参数配置
# ===============================

POOL_NUM = 100


DAYS = 30



# ===============================
# 生成数据
# ===============================

def generate_data():

    db = SessionLocal()


    try:


        print("开始生成数据...")


        # --------------------------
        # 清空旧数据
        # --------------------------

        db.query(
            WaterQuality
        ).delete()

        db.query(
            FeedingRecord
        ).delete()

        db.query(
            AlarmRecord
        ).delete()

        db.query(
            DeviceStatus
        ).delete()

        db.query(
            SeedlingQuality
        ).delete()

        db.query(
            BatchInfo
        ).delete()


        db.commit()



        # ==========================
        # 1.生成批次
        # ==========================

        for i in range(1, POOL_NUM+1):


            batch_code = f"B2026{i:03d}"

            facility_id = f"A{i:03d}"


            batch = BatchInfo(

                batch_code=batch_code,

                facility_id=facility_id,

                species="黄鳝",

                start_date=datetime.now().date()
                -
                timedelta(days=90),

                density=random.randint(
                    100,
                    200
                ),

                status="养殖中"

            )


            db.add(batch)



            # ======================
            # 2.苗种质量
            # ======================


            seedling = SeedlingQuality(

                batch_code=batch_code,

                initial_weight=random.uniform(
                    3,
                    6
                ),

                survival_rate=random.uniform(
                    85,
                    98
                ),

                health_score="良好"

            )


            db.add(seedling)



        db.commit()



        print("批次和苗种数据完成")



        # ==========================
        # 3.水质数据
        # ==========================


        for i in range(1, POOL_NUM+1):


            facility_id=f"A{i:03d}"


            for d in range(DAYS):


                time = (
                    datetime.now()
                    -
                    timedelta(days=DAYS-d)
                )


                # 默认正常数据

                oxygen=random.uniform(
                    5,
                    7
                )



                temperature=random.uniform(
                    26,
                    30
                )


                ph=random.uniform(
                    6.8,
                    7.5
                )


                ammonia=random.uniform(
                    0.01,
                    0.05
                )



                # ===================
                # 人工制造异常池
                # A001
                # ===================

                if facility_id=="A001" and d>20:


                    oxygen=random.uniform(
                        2,
                        3
                    )


                    temperature=32


                    ammonia=0.15



                water=WaterQuality(

                    facility_id=facility_id,

                    temperature=temperature,

                    ph=ph,

                    oxygen=oxygen,

                    ammonia=ammonia,

                    record_time=time

                )


                db.add(water)



        db.commit()


        print("水质数据完成")



        # ==========================
        # 4.投喂数据
        # ==========================


        for i in range(1,POOL_NUM+1):


            facility_id=f"A{i:03d}"


            for d in range(DAYS):


                eat_rate=random.uniform(
                    85,
                    98
                )


                # A001异常
                if facility_id=="A001" and d>20:

                    eat_rate=random.uniform(
                        50,
                        70
                    )


                feed=FeedingRecord(

                    facility_id=facility_id,

                    feed_amount=random.uniform(
                        5,
                        10
                    ),

                    eat_rate=eat_rate,

                    record_time=datetime.now()
                    -
                    timedelta(days=DAYS-d)

                )


                db.add(feed)



        db.commit()


        print("投喂数据完成")



        # ==========================
        # 5.报警数据
        # ==========================


        alarm=AlarmRecord(

            facility_id="A001",

            alarm_type="低溶氧",

            level="HIGH",

            alarm_time=datetime.now()

        )


        db.add(alarm)



        # ==========================
        # 6.IoT设备
        # ==========================


        for i in range(1,POOL_NUM+1):


            facility_id=f"A{i:03d}"


            device=DeviceStatus(

                facility_id=facility_id,

                device_name="增氧机",

                status="ON",

                update_time=datetime.now()

            )


            # 制造异常

            if facility_id=="A001":

                device.status="OFF"



            db.add(device)



        db.commit()


        print("全部数据生成完成")



    except Exception as e:


        db.rollback()

        print(
            "生成失败:",
            e
        )


    finally:


        db.close()




if __name__=="__main__":

    generate_data()
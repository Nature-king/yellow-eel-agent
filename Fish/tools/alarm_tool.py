from datetime import datetime, timedelta

from langchain.tools import tool

from Fish.database.mysql import SessionLocal

from Fish.database.models import (
    AlarmRecord,
    WaterQuality
)



@tool
def query_alarm_history(facility_id: str):
    """
    查询指定养殖池历史生产告警。

    参数:
        facility_id:
            养殖池编号，例如 A001

    返回:
        最近异常事件

    用于分析:
        水质异常
        设备异常
        生产风险
    """


    db = SessionLocal()


    try:


        # ==========================
        # 查询最近10条告警
        # ==========================

        alarms = (

            db.query(
                AlarmRecord
            )

            .filter(

                AlarmRecord.facility_id
                ==
                facility_id

            )

            .order_by(

                AlarmRecord.alarm_time.desc()

            )

            .limit(10)

            .all()

        )



        # 没有告警

        if not alarms:


            return {


                "status":
                    "success",


                "facility_id":
                    facility_id,


                "alarm_count":
                    0,


                "alarms":
                    []

            }



        # ==========================
        # 格式化返回
        # ==========================


        alarm_list=[]


        for alarm in alarms:


            alarm_list.append(

                {


                "type":
                    alarm.alarm_type,


                "level":
                    alarm.level,


                "time":
                    str(
                        alarm.alarm_time
                    )


                }

            )



        return {


            "status":
                "success",


            "facility_id":
                facility_id,


            "alarm_count":
                len(alarm_list),


            "alarms":
                alarm_list

        }



    finally:


        db.close()


# ==========================================
# 水质预警规则
# 以下是项目演示配置，正式使用前需要核验
# ==========================================

TEMP_MIN = 20.0
TEMP_MAX = 30.0

PH_MIN = 6.5
PH_MAX = 8.5

OXYGEN_WARNING = 3.0
OXYGEN_HIGH_RISK = 2.0

AMMONIA_MAX = 0.2

# 同类型告警24小时内不重复写入
ALARM_DEDUP_HOURS = 24

# 水质数据超过24小时，视为过期

MAX_DATA_AGE_HOURS = 24


@tool
def check_water_quality_alerts(facility_id: str):
    """
    检查指定养殖池最新水质数据，
    识别异常并写入告警记录。

    返回当前检测到的异常及新增告警数量。
    """

    db = SessionLocal()

    try:
        # 1. 查询最新水质数据
        latest = (
            db.query(WaterQuality)
            .filter(
                WaterQuality.facility_id == facility_id
            )
            .order_by(
                WaterQuality.record_time.desc()
            )
            .first()
        )

        if latest is None:
            return {
                "status": "failed",
                "facility_id": facility_id,
                "message": "没有找到该养殖池的水质数据",
                "alarm_count": 0,
                "new_alarm_count": 0,
                "alerts": []
            }


        # 1.1 检查水质数据是否过期
        sample_time = latest.record_time

        if sample_time is None:
            return {
                "status": "stale",
                "facility_id": facility_id,
                "message": "水质数据缺少监测时间，暂不生成实时预警",
                "alarm_count": 0,
                "new_alarm_count": 0,
                "alerts": []
            }

        check_time = datetime.now()
        age_seconds = (check_time - sample_time).total_seconds()

        # 数据时间在未来，视为时间异常
        if age_seconds < 0:
            return {
                "status": "invalid_time",
                "facility_id": facility_id,
                "data_time": str(sample_time),
                "message": "水质数据时间异常，暂不生成实时预警",
                "alarm_count": 0,
                "new_alarm_count": 0,
                "alerts": []
            }

        # 数据过期时，不继续检测，也不新增报警
        if age_seconds > MAX_DATA_AGE_HOURS * 3600:
            return {
                "status": "stale",
                "facility_id": facility_id,
                "data_time": str(sample_time),
                "data_age_minutes": round(age_seconds / 60, 1),
                "message": "水质监测数据已过期，暂不生成实时预警",
                "alarm_count": 0,
                "new_alarm_count": 0,
                "alerts": []
            }




        # 2. 根据规则判断异常
        alerts = []

        temperature = latest.temperature
        ph = latest.ph
        oxygen = latest.oxygen
        ammonia = latest.ammonia

        if temperature is not None:
            if temperature > TEMP_MAX:
                alerts.append({
                    "type": "HIGH_TEMP",
                    "level": "MEDIUM",
                    "value": temperature,
                    "threshold": f"<= {TEMP_MAX} ℃",
                    "message": "水温超过项目配置上限，请复核传感器并检查养殖环境。"
                })

            elif temperature < TEMP_MIN:
                alerts.append({
                    "type": "LOW_TEMP",
                    "level": "MEDIUM",
                    "value": temperature,
                    "threshold": f">= {TEMP_MIN} ℃",
                    "message": "水温低于项目配置下限，请复核水温及养殖环境。"
                })

        if ph is not None:
            if ph < PH_MIN or ph > PH_MAX:
                alerts.append({
                    "type": "ABNORMAL_PH",
                    "level": "MEDIUM",
                    "value": ph,
                    "threshold": f"{PH_MIN} - {PH_MAX}",
                    "message": "pH 超出项目配置范围，建议复测并排查水质变化原因。"
                })

        if oxygen is not None:
            if oxygen < OXYGEN_HIGH_RISK:
                alerts.append({
                    "type": "LOW_OXYGEN",
                    "level": "HIGH",
                    "value": oxygen,
                    "threshold": f">= {OXYGEN_WARNING} mg/L",
                    "message": "溶氧处于高风险区间，请立即复测并检查增氧设备。"
                })

            elif oxygen < OXYGEN_WARNING:
                alerts.append({
                    "type": "LOW_OXYGEN",
                    "level": "MEDIUM",
                    "value": oxygen,
                    "threshold": f">= {OXYGEN_WARNING} mg/L",
                    "message": "溶氧低于预警线，请检查增氧设备并加强监测。"
                })

        if ammonia is not None and ammonia >= AMMONIA_MAX:
            alerts.append({
                "type": "HIGH_AMMONIA",
                "level": "MEDIUM",
                "value": ammonia,
                "threshold": f"< {AMMONIA_MAX} mg/L",
                "message": "氨氮达到或超过项目配置上限，请复测并排查水质异常原因。"
            })

        # 3. 对同类告警做时间窗口去重
        now = datetime.now()
        cutoff = now - timedelta(
            hours=ALARM_DEDUP_HOURS
        )

        new_alarm_count = 0

        for alert in alerts:
            recent_alarm = (
                db.query(AlarmRecord.id)
                .filter(
                    AlarmRecord.facility_id == facility_id,
                    AlarmRecord.alarm_type == alert["type"],
                    AlarmRecord.alarm_time >= cutoff
                )
                .first()
            )

            alert["time"] = (
                str(latest.record_time)
                if latest.record_time
                else "未知"
            )

            alert["recorded"] = recent_alarm is None

            if recent_alarm is None:
                db.add(
                    AlarmRecord(
                        facility_id=facility_id,
                        alarm_type=alert["type"],
                        level=alert["level"],
                        alarm_time=now
                    )
                )

                new_alarm_count += 1

        # 4. 统一提交新增告警
        if new_alarm_count > 0:
            db.commit()

        return {
            "status": "success",
            "facility_id": facility_id,
            "data_time": (
                str(latest.record_time)
                if latest.record_time
                else None
            ),
            "alarm_count": len(alerts),
            "new_alarm_count": new_alarm_count,
            "alerts": alerts
        }

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()
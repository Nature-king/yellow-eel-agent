from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from Fish.tools.water_tool import query_water_quality
from Fish.tools.feeding_tool import query_feeding_record
from Fish.tools.alarm_tool import (
    query_alarm_history,
    check_water_quality_alerts
)
from Fish.tools.device_tool import query_device_status

from Fish.database.mysql import get_db
from Fish.database.models import BatchInfo


router = APIRouter(
    prefix="/farm",
    tags=["Farm"]
)


# ==========================
# 查询水质
# ==========================
@router.get("/water/{facility_id}")
def water(facility_id: str):
    return query_water_quality.invoke({
        "facility_id": facility_id
    })


# ==========================
# 查询投喂记录
# ==========================
@router.get("/feed/{facility_id}")
def feed(facility_id: str):
    return query_feeding_record.invoke({
        "facility_id": facility_id
    })


# ==========================
# 查询历史报警
# ==========================
@router.get("/alarm/{facility_id}")
def alarm(facility_id: str):
    return query_alarm_history.invoke({
        "facility_id": facility_id
    })


# ==========================
# 主动检测水质风险
# 新增接口
# ==========================
@router.get("/alerts/{facility_id}")
def alerts(facility_id: str):
    return check_water_quality_alerts.invoke({
        "facility_id": facility_id
    })


# ==========================
# 查询设备状态
# ==========================
@router.get("/device/{facility_id}")
def device(facility_id: str):
    return query_device_status.invoke({
        "facility_id": facility_id
    })


# ==========================
# 查询养殖池列表
# ==========================
@router.get("/facilities")
def facilities(
    db: Session = Depends(get_db)
):
    rows = db.query(BatchInfo).all()

    return {
        "data": [
            {
                "id": row.facility_id,
                "name": f"{row.facility_id}号养殖池"
            }
            for row in rows
        ]
    }
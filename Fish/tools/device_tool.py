from langchain.tools import tool


from Fish.database.mysql import SessionLocal

from Fish.database.models import DeviceStatus



@tool
def query_device_status(facility_id: str):
    """
    查询指定养殖池IoT设备运行状态。

    参数:
        facility_id:
            养殖池编号，例如 A001

    返回:
        当前设备状态

    用于分析:
        水质异常原因
        设备故障风险
    """

    db = SessionLocal()


    try:


        # ==========================
        # 查询设备状态
        # ==========================

        devices = (

            db.query(
                DeviceStatus
            )

            .filter(

                DeviceStatus.facility_id
                ==
                facility_id

            )

            .all()

        )


        if not devices:


            return {


                "status":
                    "failed",


                "message":
                    f"没有找到{facility_id}设备信息"

            }



        device_list=[]


        for device in devices:


            device_list.append(

                {


                "device_name":
                    device.device_name,


                "status":
                    device.status,


                "update_time":
                    str(
                        device.update_time
                    )

                }

            )



        return {


            "status":
                "success",


            "facility_id":
                facility_id,


            "devices":
                device_list

        }



    finally:

        db.close()
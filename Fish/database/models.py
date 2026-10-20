
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Float,
    Date,
    DateTime,
    Index,
    text
)
from sqlalchemy.dialects.mysql import TIMESTAMP

from Fish.database.mysql import Base


# ==========================================
# 1. 生产批次表
# 对应 MySQL：batch_info
# 对应 Tool：query_batch_info
# ==========================================

class BatchInfo(Base):

    __tablename__ = "batch_info"

    # 主键
    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # 生产批次编号，唯一
    # Agent可以通过batch_code查询批次
    batch_code = Column(
        String(50),
        unique=True,
        nullable=False
    )

    # 养殖池编号
    # 这是跨Tool参数传递的关键字段
    facility_id = Column(
        String(50),
        nullable=False
    )

    # 养殖品种
    species = Column(String(50))

    # 投苗日期
    start_date = Column(Date)

    # 养殖密度
    density = Column(Float)

    # 批次状态
    status = Column(String(20))

    # 数据创建时间，由MySQL自动生成
    create_time = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP")
    )


# ==========================================
# 2. 苗种质量表
# 对应 MySQL：seedling_quality
# 对应 Tool：query_seedling_quality
# ==========================================

class SeedlingQuality(Base):

    __tablename__ = "seedling_quality"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # 关联生产批次
    batch_code = Column(String(50))

    # 苗种初始平均重量，单位g
    initial_weight = Column(Float)

    # 苗种成活率
    # 约定使用0~100表示百分比
    survival_rate = Column(Float)

    # 健康评价
    # 例如 good、normal、poor
    health_score = Column(String(20))

    # 数据创建时间
    create_time = Column(
        TIMESTAMP,
        server_default=text("CURRENT_TIMESTAMP")
    )


# ==========================================
# 3. 水质监测表
# 对应 MySQL：water_quality
# 对应 Tool：query_water_quality
# ==========================================

class WaterQuality(Base):

    __tablename__ = "water_quality"

    # 联合索引：
    # 支持按养殖池和时间范围查询水质
    __table_args__ = (
        Index(
            "idx_facility_time",
            "facility_id",
            "record_time"
        ),
    )

    # IoT监测数据量大，使用BIGINT主键
    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    # 养殖池编号
    facility_id = Column(String(50))

    # 水温，单位℃
    temperature = Column(Float)

    # pH值
    ph = Column(Float)

    # 溶解氧，单位mg/L
    oxygen = Column(Float)

    # 氨氮，单位mg/L
    # 注意：该字段的具体氨氮口径应与数据源一致
    ammonia = Column(Float)

    # 数据采集时间
    record_time = Column(DateTime)


# ==========================================
# 4. 投喂摄食记录表
# 对应 MySQL：feeding_record
# 对应 Tool：query_feeding_record
# ==========================================

class FeedingRecord(Base):

    __tablename__ = "feeding_record"

    # 按养殖池查询投喂记录的索引
    __table_args__ = (
        Index(
            "idx_feed_facility",
            "facility_id"
        ),
    )

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    # 养殖池编号
    facility_id = Column(String(50))

    # 单次投喂重量，单位kg
    feed_amount = Column(Float)

    # 摄食率
    # 使用0~100表示百分比
    eat_rate = Column(Float)

    # 投喂记录时间
    record_time = Column(DateTime)


# ==========================================
# 5. 生产告警记录表
# 对应 MySQL：alarm_record
# 对应 Tool：query_alarm_history
# ==========================================

class AlarmRecord(Base):

    __tablename__ = "alarm_record"

    id = Column(
        BigInteger,
        primary_key=True,
        autoincrement=True
    )

    # 发生告警的养殖池
    facility_id = Column(String(50))

    # 告警类型
    # 例如 LOW_OXYGEN、HIGH_TEMP
    alarm_type = Column(String(50))

    # 告警等级
    # 例如 LOW、MEDIUM、HIGH
    level = Column(String(20))

    # 告警发生时间
    alarm_time = Column(DateTime)


# ==========================================
# 6. IoT设备状态表
# 对应 MySQL：device_status
# 对应 Tool：query_device_status
# ==========================================

class DeviceStatus(Base):

    __tablename__ = "device_status"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True
    )

    # 设备所属养殖池
    facility_id = Column(String(50))

    # 设备名称
    # 例如 oxygen_machine、water_pump
    device_name = Column(String(50))

    # 设备运行状态
    # 例如 ON、OFF、FAULT
    status = Column(String(20))

    # 最近状态更新时间
    update_time = Column(DateTime)
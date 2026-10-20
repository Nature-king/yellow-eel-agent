
# Fish/agent/router.py

import re
import unicodedata


# 明确的养殖业务对象
FARM_WORDS = [
    "养殖池", "池子", "本池", "该池", "这个池",
    "黄鳝", "鳝鱼", "批次",
    "水质", "溶氧", "氨氮", "ph",
    "投喂", "摄食", "增氧机",
    "苗种", "养殖设备", "养殖风险"
]

# 与数据库有关的指标或业务
DATA_WORDS = [
    "水质", "溶氧", "氧气", "氨氮",
    "ph", "投喂", "摄食",
    "报警", "告警", "设备",
    "增氧机", "苗种", "批次",
    "存活率", "水温", "养殖状态"
]

# 当前数据查询词
DATA_INTENTS = [
    "当前", "现在", "实时", "今天",
    "今日", "昨天", "昨晚", "最近",
    "历史", "趋势", "走势", "记录",
    "查询", "查看", "多少", "正常吗",
    "怎么样", "有没有", "状态"
]

# 专业知识与养殖方法
RAG_WORDS = [
    "怎么养", "如何养", "适宜",
    "适合", "正常范围", "适宜范围",
    "标准", "要求", "为什么",
    "什么原因", "怎么办", "怎么处理",
    "如何处理", "预防", "防治",
    "疾病", "病害", "症状",
    "饲料", "养殖技术", "养殖方法",
    "有什么影响",
    "什么影响",
    "产生什么影响",
    "会产生什么影响",
    "有什么危害",
    "什么危害",
    "有何危害",
    "会导致什么",
    "有什么后果",
    "什么后果",
    "有哪些影响",
]

# 明确需要实时外部信息的主题
WEB_WORDS = [
    "天气", "天气预报", "气温预报",
    "新闻", "热搜", "股价", "股票行情",
    "汇率", "实时汇率", "最新消息",
    "网上搜索", "联网搜索", "搜索网页",
    "航班动态"
]

# 需要当前信息的网络问题
WEB_TIME_WORDS = [
    "今天", "今日", "现在", "当前",
    "实时", "最新", "最近", "明天",
    "后天", "本周"
]

# 养殖当前状态询问
CURRENT_FARM_WORDS = [
    "当前养殖池", "本池", "这个池",
    "该池", "当前水质", "当前溶氧"
]


def classify_question(question: str) -> str:
    """
    返回：
        database: 养殖数据查询与分析
        rag:      黄鳝专业知识
        web:      需要联网的实时外部信息
        chat:     普通聊天
    """

    if not isinstance(question, str):
        return "chat"

    q = unicodedata.normalize(
        "NFKC", question
    ).strip().lower()

    if not q:
        return "chat"

    has_farm = any(w in q for w in FARM_WORDS)
    has_data = any(w in q for w in DATA_WORDS)
    has_data_intent = any(
        w in q for w in DATA_INTENTS
    )
    has_rag = any(w in q for w in RAG_WORDS)
    has_web = any(w in q for w in WEB_WORDS)
    has_web_time = any(
        w in q for w in WEB_TIME_WORDS
    )

    # 1. 用户明确提出联网查询
    if any(w in q for w in [
        "联网搜索", "网上搜索", "搜索网页"
    ]):
        return "chat"

    # 2. 明确的外部实时问题
    # 如北京天气、今日新闻、股票行情
    if has_web:
        return "chat"

    # 3. 明确的批次或养殖池编号
    # 匹配养殖池编号，例如 A001、B002、B2026001
    # 允许编号前后紧邻中文
    has_identifier = bool(
        re.search(r"(?<![a-z0-9])[a-z]\d{3,}(?![a-z0-9])", q)
    )
    # 明确针对养殖池或生产批次生成分析报告
    REPORT_WORDS = [
        "分析报告",
        "综合报告",
        "详细报告",
        "完整报告",
        "养殖报告",
        "状态报告",
        "风险报告",
        "全面分析",
        "综合分析",
        "详细分析"
    ]

    if (
            has_identifier
            and any(word in q for word in REPORT_WORDS)
    ):
        return "database"

    # 4. 养殖池具体数据查询或诊断
    if has_identifier and (
        has_data or has_data_intent
        or "养殖池" in q or "批次" in q
    ):
        return "database"

    if any(w in q for w in CURRENT_FARM_WORDS):
        return "database"

    # 明确询问养殖标准、适宜范围等专业知识
    # 优先进入RAG，避免“多少”等词触发数据库查询
    knowledge_intents = [
        "适宜",
        "适合",
        "正常范围",
        "适宜范围",
        "标准是多少",
        "多少合适",
        "养殖要求",
        "温度要求",
        "水质要求"
    ]

    current_data_intents = [
        "当前",
        "现在",
        "实时",
        "本池",
        "这个池",
        "该池",
        "最近监测",
        "最新数据"
    ]

    if (
            any(word in q for word in knowledge_intents)
            and not any(word in q for word in current_data_intents)
            and not has_identifier
    ):
        return "rag"


    # 5. 当前养殖数据问题
    if has_data and has_data_intent:
        return "database"

    # 6. 专业知识问题
    if has_rag and (
        has_farm or has_data
    ):
        return "rag"

    # 7. 未包含时间词的养殖业务状态问题
    if has_data:
        return "database"

    # 8. 需要实时外部信息的通用问题
    if has_web_time and any(w in q for w in [
        "发生什么", "有什么大事", "重大事件",
        "比赛结果", "实时情况"
    ]):
        return "chat"

    # 9. 其他普通对话
    return "chat"
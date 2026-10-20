from dotenv import load_dotenv

load_dotenv()

from langchain.agents import (
    create_tool_calling_agent,
    AgentExecutor
)

from langchain_core.prompts import (
    ChatPromptTemplate,
    MessagesPlaceholder
)

from langchain_core.messages import (
    HumanMessage,
    AIMessage,
    SystemMessage
)

from Fish.memory.redis_memory import RedisMessageHistory
from Fish.agent.llm import llm

# =========================
# 导入业务Tool
# =========================

from Fish.tools.batch_tool import query_batch_info
from Fish.tools.seedling_tool import query_seedling_quality
from Fish.tools.water_tool import query_water_quality
from Fish.tools.feeding_tool import query_feeding_record
from Fish.tools.alarm_tool import query_alarm_history
from Fish.tools.device_tool import query_device_status
from Fish.tools.rag_tool import query_aquaculture_knowledge

import time
from langchain_core.callbacks import BaseCallbackHandler
import re
import json
from types import SimpleNamespace

class PerformanceCallback(BaseCallbackHandler):
    """统计本轮LLM和Tool的执行耗时。"""

    def __init__(self):
        super().__init__()
        self.llm_starts = {}
        self.tool_starts = {}

        self.llm_count = 0
        self.tool_count = 0

        self.llm_durations = []
        self.tool_durations = []

    def on_chat_model_start(
        self, serialized, messages, *,
        run_id, **kwargs
    ):
        self.llm_count += 1
        self.llm_starts[run_id] = time.perf_counter()

    def on_llm_start(
        self, serialized, prompts, *,
        run_id, **kwargs
    ):
        self.llm_count += 1
        self.llm_starts[run_id] = time.perf_counter()

    def on_llm_end(
        self, response, *,
        run_id, **kwargs
    ):
        start = self.llm_starts.pop(run_id, None)

        if start is not None:
            duration = time.perf_counter() - start
            self.llm_durations.append(duration)
            print(
                f"[LLM单次耗时] 第{len(self.llm_durations)}次: "
                f"{duration:.2f}秒"
            )

    def on_tool_start(
        self, serialized, input_str, *,
        run_id, **kwargs
    ):
        self.tool_count += 1
        self.tool_starts[run_id] = (
            serialized.get("name", "unknown"),
            time.perf_counter()
        )

    def on_tool_end(
        self, output, *,
        run_id, **kwargs
    ):
        info = self.tool_starts.pop(run_id, None)

        if info:
            tool_name, start = info
            duration = time.perf_counter() - start

            self.tool_durations.append(
                (tool_name, duration)
            )

    def print_report(self):
        print(
            f"[性能统计] LLM调用: {self.llm_count}次 | "
            f"累计耗时: {sum(self.llm_durations):.2f}秒"
        )

        print(
            f"[性能统计] Tool调用: {self.tool_count}次 | "
            f"累计耗时: "
            f"{sum(d for _, d in self.tool_durations):.2f}秒"
        )

        for name, duration in self.tool_durations:
            print(
                f"[Tool耗时] {name}: {duration:.3f}秒"
            )


def get_required_tools(question: str):
    """按本轮问题确定必须获得的业务数据；通用知识问答不强制查询数据库。"""
    q = question.strip().lower()
    required = set()

    # 必须明确地问到本池/记录/最新数据，才将知识问答当成业务数据问题。
    # 仅提及“溶氧、水温”等指标不等于在询问具体养殖池。
    data_context_words = (
        "当前", "现在", "最新", "最近", "记录", "监测", "数据", "这个池",
        "本池", "该池", "我池", "我的池", "养殖池", "池号", "批次",
        "综合分析", "报告", "今天", "昨日", "昨天", "上次",
    )
    facility_code = bool(re.search(r"(?<![a-z0-9])[a-z]\d{3,}(?![a-z0-9])", q))
    explicitly_data = facility_code or any(w in q for w in data_context_words)

    knowledge_patterns = (
        "什么是", "有哪些风险", "哪些风险", "有什么风险", "有哪些危害",
        "有什么危害", "如何预防", "怎么预防", "养殖原理", "养殖知识",
        "一般来说", "通常", "常见原因", "如何防治", "为什么会",
    )
    if any(w in q for w in knowledge_patterns) and not explicitly_data:
        return set()

    if any(w in q for w in ("水质", "水温", "溶氧", "氨氮", "ph")):
        required.add("query_water_quality")
    if any(w in q for w in ("投喂", "摄食", "喂食")):
        required.add("query_feeding_record")
    if any(w in q for w in ("设备", "增氧机")):
        required.add("query_device_status")
    if any(w in q for w in ("告警", "报警")):
        required.add("query_alarm_history")
    if any(w in q for w in ("苗种", "成活率")):
        required.add("query_seedling_quality")

    if any(w in q for w in (
        "完整报告", "详细报告", "综合报告", "完整详细分析报告"
    )):
        required.update({
            "query_water_quality", "query_feeding_record",
            "query_device_status", "query_alarm_history"
        })
    return required


def validate_tool_result(tool_name, observation, facility_id):
    """
    校验业务Tool返回结果。
    返回：(是否有效, 原因)
    """

    if not isinstance(observation, dict):
        return False, "工具返回值不是字典"

    if observation.get("status") != "success":
        return False, "工具查询未成功"

    # 校验养殖池编号
    returned_id = observation.get("facility_id")

    if returned_id is not None:
        if str(returned_id) != str(facility_id):
            return False, "查询养殖池编号不一致"

    # 水质数据
    if tool_name == "query_water_quality":
        if not observation.get("latest"):
            return False, "缺少最新水质记录"

    # 投喂数据
    elif tool_name == "query_feeding_record":
        if not observation.get("latest"):
            return False, "缺少投喂记录"

    # 设备数据
    elif tool_name == "query_device_status":
        if not observation.get("devices"):
            return False, "缺少设备记录"

    # 告警记录允许为空
    elif tool_name == "query_alarm_history":
        if "alarms" not in observation:
            return False, "缺少告警查询结果字段"

    return True, "success"

def check_required_tool_results(question, facility_id, intermediate_steps):
    """
    检查本轮必要业务Tool是否返回有效结果。
    返回：(是否通过, 有效工具集合, 缺失工具集合, 失败记录)
    """

    required_tools = get_required_tools(question)

    validated_tools = set()
    failed_tools = []

    supported_tools = {
        "query_water_quality",
        "query_feeding_record",
        "query_device_status",
        "query_alarm_history",
    }

    for action, observation in intermediate_steps:
        tool_name = action.tool

        if tool_name not in supported_tools:
            continue

        is_valid, reason = validate_tool_result(
            tool_name,
            observation,
            facility_id
        )

        if is_valid:
            validated_tools.add(tool_name)
        else:
            failed_tools.append((tool_name, reason))
            print(
                f"[Tool失败详情] "
                f"工具={tool_name} | "
                f"原因={reason} | "
                f"调用参数={getattr(action, 'tool_input', None)} | "
                f"返回结果={str(observation)[:500]}"
            )

    missing_tools = required_tools - validated_tools

    print(
        f"[Tool结果校验] 有效: {sorted(validated_tools)} | "
        f"失败: {failed_tools}"
    )

    print(
        f"[Tool校验] 必需: {sorted(required_tools)} | "
        f"有效: {sorted(validated_tools)} | "
        f"缺失: {sorted(missing_tools)}"
    )

    passed = len(missing_tools) == 0

    return passed, validated_tools, missing_tools, failed_tools

def auto_query_missing_tools(
    missing_tools,
    facility_id
):
    """
    自动补查缺失的核心业务Tool。

    返回：
        successful: 成功的查询结果字典
        failed: 失败的工具及原因
    """

    tool_map = {
        "query_water_quality": query_water_quality,
        "query_feeding_record": query_feeding_record,
        "query_device_status": query_device_status,
        "query_alarm_history": query_alarm_history
    }

    successful = {}
    failed = {}

    for tool_name in sorted(missing_tools):

        tool = tool_map.get(tool_name)

        if tool is None:
            failed[tool_name] = "暂不支持自动补查"
            continue

        print(f"[自动补查] 开始: {tool_name}")

        try:
            observation = tool.invoke({
                "facility_id": facility_id
            })

            is_valid, reason = validate_tool_result(
                tool_name,
                observation,
                facility_id
            )

            if is_valid:
                successful[tool_name] = observation
                print(f"[自动补查] 成功: {tool_name}")
            else:
                failed[tool_name] = reason
                print(
                    f"[自动补查] 失败: "
                    f"{tool_name} | {reason}"
                )

        except Exception as e:
            failed[tool_name] = str(e)
            print(
                f"[自动补查] 异常: "
                f"{tool_name} | {repr(e)}"
            )

    return successful, failed



def build_data_context(intermediate_steps, facility_id):
    """
    整理本轮已经成功查询的养殖业务数据。
    为模型提供数据时间和证据边界。

    仅处理已确认返回结构的核心业务Tool。
    """

    context = {}

    supported_tools = {
        "query_water_quality",
        "query_feeding_record",
        "query_device_status",
        "query_alarm_history"
    }

    for action, observation in intermediate_steps:

        tool_name = action.tool

        if tool_name not in supported_tools:
            continue

        is_valid, reason = validate_tool_result(
            tool_name,
            observation,
            facility_id
        )

        if not is_valid:
            continue

        if tool_name == "query_water_quality":

            latest = observation.get("latest", {})

            context["水质"] = {
                "record_time": latest.get("time"),
                "latest_record": latest,
                "trend": observation.get("trend", []),
                "interpretation": (
                    "这是系统中最近一条水质监测记录，"
                    "不代表数据采集后没有发生变化。"
                )
            }

        elif tool_name == "query_feeding_record":

            latest = observation.get("latest", {})

            context["投喂"] = {
                "record_time": latest.get("time"),
                "latest_record": latest,
                "trend": observation.get("trend", []),
                "interpretation": (
                    "这是最近一条投喂记录，"
                    "不得直接称为今日投喂或当前摄食率。"
                )
            }

        elif tool_name == "query_device_status":

            devices = observation.get("devices", [])

            context["设备"] = {
                "devices": devices,
                "interpretation": (
                    "设备状态仅代表对应update_time时刻的记录。"
                    "不得据此推断设备此后一直开启或关闭。"
                )
            }

        elif tool_name == "query_alarm_history":

            context["告警"] = {
                "alarm_count": observation.get(
                    "alarm_count", 0
                ),
                "alarms": observation.get("alarms", []),
                "interpretation": (
                    "告警记录属于历史事件，"
                    "不能直接证明异常当前仍然存在。"
                )
            }

    return context


def check_answer_consistency(answer: str, context: dict):
    """
    基于规则的回答风险筛查。

    检查：
    1. 设备持续状态推断
    2. 历史投喂数据被当作当前数据
    3. 未证实的确定性因果关系
    4. 传感器故障的过度确定判断
    5. 药剂使用建议

    返回风险列表，不直接修改回答。
    """
    if not isinstance(answer, str) or not answer.strip():
        return [{
            "type": "empty_answer",
            "message": "AI回答为空",
            "text": ""
        }]

    issues = []

    # 先按句号、换行等分割，再按逗号、分号细分
    # 这样可以减少同一句中不同含义的相互干扰
    sentences = [
        part.strip()
        for sentence in re.split(r"[。！？\n]+", answer)
        for part in re.split(r"[，,；;]+", sentence)
        if part.strip()
    ]



    def add_issue(issue_type, message, sentence):
        issues.append({
            "type": issue_type,
            "message": message,
            "text": sentence
        })

    def has_uncertainty(sentence):
        return bool(re.search(
            r"可能|疑似|推测|尚需|有待|待核实|"
            r"不能确定|无法确认|尚不明确|"
            r"不排除|假设|如果|若",
            sentence
        ))

    def is_negated(sentence, keyword):
        """
        只判断紧邻关键词的否定表达。
        避免整句话只要出现'不要'就跳过检查。
        """
        pos = sentence.find(keyword)
        if pos < 0:
            return False

        prefix = sentence[max(0, pos - 15):pos]

        return bool(re.search(
            r"(不要|不得|禁止|避免|不应|切勿|"
            r"无需|不建议|不宜|不能|勿)"
            r".{0,10}$",
            prefix
        ))

    # =========================================
    # 1. 设备持续状态推断
    # =========================================
    if context.get("设备"):
        duration_pattern = re.compile(
            r"(一直|始终|长期|持续|自.{0,20}起)"
            r".{0,25}"
            r"(关闭|停机|未运行|OFF|开启|运行)",
            re.IGNORECASE
        )

        for sentence in sentences:
            if not any(w in sentence for w in [
                "增氧机", "设备"
            ]):
                continue

            # 排除明确的未来操作建议
            advice_pattern = (
                    r"建议|应当|应该|需要|保持|维持|"
                    r"尽量|确保|注意"
                )

            if re.search(advice_pattern, sentence):
                continue


            if duration_pattern.search(sentence):
                if not has_uncertainty(sentence):
                    add_issue(
                        "device_duration",
                        "可能将单次设备状态推断为持续状态",
                        sentence
                    )

    # =========================================
    # 2. 历史摄食率被描述为当前数据
    # =========================================
    if context.get("投喂"):
        current_rate_pattern = re.compile(
            r"(目前|当前|现在|今日|今天)"
            r"(?:的|实际|最新|记录)?"
            r".{0,10}"
            r"摄食率"
            r".{0,12}"
            r"(?:为|是|达到|降至|仅为|约为|[:：])"
            r"\s*\d+(?:\.\d+)?\s*%"
            r"|"
            r"摄食率"
            r".{0,10}"
            r"(?:目前|当前|现在)"
            r".{0,10}"
            r"(?:为|是|达到|降至)"
            r"\s*\d+(?:\.\d+)?\s*%"
        )

        for sentence in sentences:
            if "摄食率" not in sentence:
                continue

            if current_rate_pattern.search(sentence):
                if not has_uncertainty(sentence):
                    add_issue(
                        "feeding_freshness",
                        "可能将历史摄食率描述为当前值",
                        sentence
                    )

    # =========================================
    # 3. 确定性因果关系
    # =========================================
    causal_patterns = [
        r"直接导致",
        r"必然导致",
        r"根本原因是",
        r"确定是.{0,30}导致",
        r"已经证实",
        r"正是由于",
        r"是.{1,35}的直接原因",
        r"归因于",
        r"由.{1,35}造成",
        r"导致.{0,25}的直接原因"
    ]

    for sentence in sentences:
        if has_uncertainty(sentence):
            continue

        if any(re.search(p, sentence) for p in causal_patterns):
            add_issue(
                "causality",
                "包含需要证据支持的确定性因果判断",
                sentence
            )

    # =========================================
    # 4. 传感器故障确定性判断
    # =========================================
    certainty_words = [
        "极大概率",
        "必定",
        "肯定是",
        "确定为",
        "确认是",
        "毫无疑问"
    ]

    for sentence in sentences:
        if not any(w in sentence for w in [
            "传感器", "探头", "pH计"
        ]):
            continue

        # “确认是否为故障”是核实建议，不是确定性诊断
        if re.search(r"(?:确认|检查|排查|核实)(?:一下)?是否", sentence):
            continue

        if any(w in sentence for w in certainty_words):
            add_issue(
                "sensor_certainty",
                "传感器故障判断可能过于确定",
                sentence
            )

    # =========================================
    # 5. 化学药剂使用建议
    # =========================================
    chemical_words = [
        "磷酸二氢钠",
        "生石灰",
        "熟石灰",
        "石灰",
        "酸性调节剂",
        "碱性调节剂",
        "化学调节剂",
        "缓冲剂",
        "抗应激药物",
        "泼洒药物",
        "酸性物质"
    ]

    action_words = [
        "建议",
        "使用",
        "投加",
        "投放",
        "添加",
        "泼洒",
        "施用",
        "立即",
        "调节",
        "处理",
        "采用"
    ]

    for sentence in sentences:
        for chemical in chemical_words:
            if chemical not in sentence:
                continue

            # 如明确提出禁止或避免使用该药剂，
            # 不按药剂使用建议拦截
            if is_negated(sentence, chemical):
                continue

            if any(w in sentence for w in action_words):
                add_issue(
                    "chemical_advice",
                    "包含需要专业核实的药剂建议",
                    sentence
                )
                break

    # =========================================
    # 6. 摄食率持续状态推断
    # =========================================
    if context.get("投喂"):
        for sentence in sentences:
            if "摄食率" not in sentence:
                continue

            duration_pattern = (
                r"(长期|一直|始终|持续)"
                r".{0,20}"
                r"(维持|保持|处于|徘徊)"
                r".{0,20}"
                r"\d+(?:\.\d+)?\s*%"
                r"|"
                r"摄食率.{0,12}"
                r"(长期|一直|始终|持续)"
                r".{0,20}"
                r"\d+(?:\.\d+)?\s*%"
            )

            if re.search(duration_pattern, sentence):
                if not has_uncertainty(sentence):
                    add_issue(
                        "feeding_duration",
                        "可能将历史摄食率推断为长期持续状态",
                        sentence
                    )


    # =========================================
    # 7. 不同记录时间的设备与水质比较
    # =========================================
    water = context.get("水质")
    device = context.get("设备")
    if water and device:
        water_time = water.get("record_time")
        device_times = [
            item.get("update_time")
            for item in device.get("devices", [])
            if item.get("update_time")
        ]
        # 有历史设备记录的情况十分常见，仅凭时间不同不能判定回答错误；
        # 同时出现具体的时间冲突断言时才进行启发式拦截。
        if water_time and device_times and all(t != water_time for t in device_times):
            for sentence in re.split(r"[。！？\n]+", answer):
                if not (any(w in sentence for w in ("设备", "增氧机"))
                        and any(w in sentence for w in ("溶氧", "溶解氧"))):
                    continue
                if any(w in sentence for w in (
                    "时间不同", "不同时间", "不能直接比较", "无法直接比较",
                    "无法据此判断", "不能据此判断", "需关注", "建议关注",
                    "避免再次", "防止再次", "预防"
                )):
                    continue
                if any(w in sentence for w in ("同时", "与此同时", "同一时刻", "矛盾", "不一致")):
                    add_issue(
                        "cross_time_comparison",
                        "可能将不同时间的设备与水质记录作为同时状态比较",
                        sentence.strip()
                    )

    # 8. 与项目已配置的氨氮阈值直接矛盾的表述
    water_record = (context.get("水质") or {}).get("latest_record") or {}
    ammonia = water_record.get("ammonia")
    try:
        ammonia_value = float(ammonia) if ammonia is not None else None
    except (TypeError, ValueError):
        ammonia_value = None
    if ammonia_value is not None and ammonia_value >= 0.2:
        for sentence in sentences:
            if ("氨氮" in sentence and
                    any(w in sentence for w in (
                        "可接受范围", "正常范围", "尚属正常", "并未超标", "未超标"
                    ))):
                add_issue(
                    "threshold_mismatch",
                    "氨氮记录达到项目预警阈值0.2 mg/L，却被描述为正常",
                    sentence
                )

    # 所有情况都必须返回列表（含只有水质记录的情况）
    return issues

def build_safe_fallback_answer(data_context: dict) -> str:
    """
    根据已验证业务数据构建保守的事实摘要。

    不调用LLM，不使用被拦截的原始回答。
    不推断当前实时状态或未经证实的因果关系。
    """
    lines = [
        "本轮AI分析包含需要核实的判断。"
        "以下仅展示已查询到的业务记录："
    ]

    water = data_context.get("水质")
    if water:
        latest = water.get("latest_record") or {}
        record_time = water.get("record_time") or "时间未知"

        fields = [
            ("水温", "temperature", "℃"),
            ("pH", "ph", ""),
            ("溶氧", "oxygen", " mg/L"),
            ("氨氮", "ammonia", " mg/L")
        ]

        values = []
        for label, key, unit in fields:
            value = latest.get(key)
            if value is not None:
                values.append(f"{label}{value}{unit}")

        if values:
            lines.append(
                f"\n【水质记录】{record_time}："
                + "，".join(values)
                + "。"
            )

    feeding = data_context.get("投喂")
    if feeding:
        latest = feeding.get("latest_record") or {}
        record_time = feeding.get("record_time") or "时间未知"

        values = []

        amount = latest.get("feed_amount")
        if amount is not None:
            values.append(f"投喂量{amount:.2f} kg")

        rate = latest.get("eat_rate")
        if rate is not None:
            values.append(f"摄食率{rate:.1f}%")

        if values:
            lines.append(
                f"\n【投喂记录】{record_time}："
                + "，".join(values)
                + "。"
            )

    device = data_context.get("设备")
    if device:
        devices = device.get("devices", [])

        latest_devices = {}

        for item in devices:
            name = item.get("device_name", "未知设备")
            record_time = item.get("update_time") or ""

            old_item = latest_devices.get(name)

            if (
                    old_item is None
                    or record_time > (
                    old_item.get("update_time") or ""
            )
            ):
                latest_devices[name] = item

        for name, item in latest_devices.items():
            status = item.get("status", "未知")
            update_time = item.get(
                "update_time", "时间未知"
            )

            lines.append(
                f"\n【设备最新记录】{name}："
                f"{update_time}记录状态为{status}。"
            )

    alarm = data_context.get("告警")
    if alarm:
        alarm_count = alarm.get("alarm_count")
        if alarm_count is not None:
            lines.append(
                f"\n【告警记录】查询结果包含"
                f"{alarm_count}条告警记录。"
                "这些记录不代表当前仍存在告警。"
            )

    if len(lines) == 1:
        return (
            "本轮分析未能通过事实校验，"
            "且缺少可用于生成可靠摘要的业务数据。"
            "请核查查询结果后重试。"
        )

    lines.append(
        "\n【说明】以上为系统保存的最近记录，"
        "不等于当前实时状态。"
        "如果记录存在异常或时间较早，"
        "应优先人工复测、核对设备实际状态，"
        "并结合更新的数据进一步判断。"
        "不要仅依据单次异常记录自行投加化学制剂。"
    )

    return "\n".join(lines)


def generate_verified_answer(
    question,
    facility_id,
    verified_data
):
    """
    根据本轮成功查询的业务数据重新生成回答。
    不依赖Redis中的旧报告数据。
    """

    messages = [
        SystemMessage(content=(
            "你是黄鳝智慧养殖辅助决策助手。\n"
            "请严格依据本轮提供的业务数据回答问题。\n"
            "禁止使用历史对话中的旧数值代替本轮数据。\n"
            "不得编造数据、告警等级或监测时间。\n"
            "必须区分历史记录与当前状态。\n"
            "不能根据设备最后一条OFF记录推断一直关闭。\n"
            "不能将数据相关性直接解释为因果关系。\n"
            "对可能故障应说明需要复测核实。\n"
            "不得推荐未经验证的药剂或具体剂量。\n"
            "简单查询简洁回答，综合分析使用三个部分，"
            "明确要求完整报告时使用五章节结构。\n"
            "不要输出JSON，只输出最终中文回答。"
        )),
        HumanMessage(content=(
            f"养殖池：{facility_id}\n"
            f"用户问题：{question}\n\n"
            "本轮已验证的业务数据：\n"
            + json.dumps(
                verified_data,
                ensure_ascii=False,
                default=str
            )
        ))
    ]

    response = llm.invoke(messages)
    answer = response.content

    if not isinstance(answer, str):
        raise ValueError(
            "模型返回的回答不是文本"
        )

    if not answer.strip():
        raise ValueError(
            "模型返回空回答"
        )

    return answer



# =========================
# Tool列表：保持不变
# =========================

tools = [
    query_batch_info,
    query_seedling_quality,
    query_water_quality,
    query_feeding_record,
    query_alarm_history,
    query_device_status,
    query_aquaculture_knowledge
]


# =========================
# Agent提示词：优化版
# =========================



SYSTEM_PROMPT = """
你是黄鳝智慧养殖辅助决策Agent。
本系统使用MySQL中的模拟养殖业务数据，用于展示智能查询、状态分析和辅助决策能力。

你的任务是根据用户问题，自主调用必要的业务Tool或养殖知识库，
基于真实查询结果提供准确、有依据、专业且可执行的中文回答。

【一、工具调用规则】

1. 涉及具体养殖池的当前、最新、历史或综合业务数据时，
   必须调用本轮相关Tool，不得直接使用Redis中的旧数值回答。

2. 根据问题选择必要工具：
   - query_batch_info：批次信息与养殖池关联
   - query_seedling_quality：苗种质量、成活率
   - query_water_quality：水质指标及历史趋势
   - query_feeding_record：投喂量与摄食率
   - query_alarm_history：历史告警
   - query_device_status：设备状态记录
   - query_aquaculture_knowledge：养殖专业知识

3. 简单问题只查询必要数据。
   综合分析按照用户明确提到的业务维度选择工具。
   完整报告应覆盖可查询的主要业务维度。

4. 用户提供batch_code时，先通过批次Tool确认关联养殖池。
   用户明确指定facility_id时，以本轮指定为准。
   “这个池”“它”等指代可结合当前输入与历史对话理解。

5. Redis历史仅用于理解上下文和用户意图。
   本轮Tool查询结果始终优先于历史回答。
   Tool失败、数据缺失时如实说明，不得自行补全。

【二、数据真实性与时效性】

1. 所有业务数值、设备状态和记录时间必须来自本轮Tool结果。
   不得编造监测数值、变化幅度、告警等级或设备运行历史。

2. Tool中的latest表示该数据源最近一条记录，
   不一定代表真实世界的实时状态。

3. 引用关键业务数据时，应明确标注对应记录时间。
   同一组记录可以统一标注时间，无须对每个数值重复说明。

4. 区分以下概念：
   - 水质：最近监测记录及历史趋势
   - 投喂：最近投喂记录及历史变化
   - 设备：最后一次记录的状态
   - 告警：系统保存的历史告警

5. 不同时间的设备、水质和投喂记录不能当作同一时刻的状态。
   例如，10月11日设备OFF与10月18日溶氧正常，
   不构成设备状态与水质数据的逻辑矛盾。

6. 单条设备ON或OFF记录只能证明该记录时刻的状态。
   不得据此推断设备一直运行、长期停机或具体启停时间。

7. 数据库为模拟业务数据。
   可以分析模拟养殖场景中的最新记录和历史变化，
   但不得宣称数据来自真实在线传感器。
   不得仅因模拟记录日期较早就认定系统离线或设备故障。

【三、事实分析与风险判断】

分析必须区分三个层次：

- 已知事实：Tool直接返回的数据、时间和可计算的变化。
- 风险推测：依据数据提出的潜在风险或可能原因。
- 待核实事项：现有记录无法直接证明、需要进一步检查的问题。

必须遵守：

1. 可以描述指标升高、降低、异常或改善，
   但不能把相关性直接认定为因果关系。

2. 不得仅凭摄食率改善就认定黄鳝健康、
   增重、生长状态或消化功能已经恢复。

3. 不得仅凭设备由OFF记录变为ON记录，
   就断言设备已经连续运行或直接导致溶氧改善。

4. 不得根据少量历史记录断言某个状态长期持续。
   历史趋势分析应与Tool提供的记录范围一致。

5. 水温、pH等指标突变时，可以提示异常风险，
   但不能未经核实就断定传感器损坏、疾病或污染原因。

6. 不得编造传感器故障概率、行业阈值、
   风险等级、疾病诊断或管理操作记录。
   项目已配置氨氮达到0.2 mg/L即预警，不能把0.35 mg/L说成正常。

7. 风险等级优先依据Tool或系统已有规则。
   没有明确规则时，采用定性描述，不虚构评级标准。

8. 养殖建议应与已知数据相匹配。
   优先建议复测异常指标、核查设备、观察养殖状态、
   补充监测及记录管理。

9. 不推荐未经验证的药物、化学调节剂、
   生石灰等具体制剂或使用剂量。
   对无法确认的处理措施，建议由专业人员评估。

10. 可以提出合理的未来管理建议，
    但必须明确这是建议，而不是已经发生的事实。

【四、按问题类型控制回答】

A. 简单数据查询
例如：“A001当前溶氧是多少？”

- 直接给出最近记录的数值和时间。
- 通常1～3句话。
- 不生成报告或添加无关分析。

B. 一般状态查询
例如：“A001水质怎么样？”

- 总体判断。
- 关键数据及时间。
- 主要异常与必要建议。
- 通常100～200字。

C. 原因分析与风险处理
例如：“为什么摄食率下降？”

按照以下顺序：
1. 主要判断
2. 数据依据
3. 可能原因及证据限制
4. 优先处理建议

通常200～350字。

D. 普通综合分析
例如：“综合分析A001的水质、投喂和设备。”

默认结构：

### 1. 状态概览
展示各业务维度的最新记录、时间及历史变化。

### 2. 主要风险
分析2～3项最重要的问题，
区分已确认异常和可能风险。

### 3. 处理建议
按照优先级给出3～5条可执行建议。

通常300～500字。
不自动扩展为完整五章节报告。

E. 完整详细报告

仅当用户明确要求“完整报告”“详细报告”
“全面分析报告”等内容时使用：

## 养殖池综合分析报告

### 1. 基本情况与数据概览
### 2. 水质及养殖状态分析
### 3. 风险识别与原因分析
### 4. 管理与调控建议
### 5. 综合结论

报告应覆盖已查询到的相关业务维度，
内容充分但不重复。
缺少数据的维度应明确说明，不得编造。

F. 专业知识问题

根据需要调用query_aquaculture_knowledge。
知识库用于解释养殖原理、风险及管理方法，
不能代替数据库中的具体养殖池记录。
不得虚构文献、标准或知识来源。

【五、多轮对话】

1. Redis历史用于理解上下文，不是最新业务数据来源。
2. 涉及当前或最新业务数据时，重新调用相关Tool。
3. 用户本轮明确指定的养殖池优先于历史指代。
4. 本轮查询结果与历史回答冲突时，以本轮结果为准。
5. 不将历史回答中的推断当成已证实的业务事实。

【六、最终输出要求】

1. 使用专业、自然、简洁的中文。
2. 先回答用户最关心的问题，再解释数据依据。
3. 数值必须准确，时间必须对应。
4. 分析要有实际价值，不只罗列数据。
5. 区分已知事实、风险推测和待核实事项。
6. 简单问题简短回答，详细报告保持必要深度。
7. 不重复相同规则、数值和结论。
8. 不输出内部推理、工具调用过程或JSON。
9. 不为了填充篇幅编造内容。
"""




prompt = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),

        # Redis历史消息作为独立对话消息传入
        MessagesPlaceholder(
            variable_name="chat_history",
            optional=True
        ),

        ("human", "{input}"),

        # Agent内部工具调用记录
        MessagesPlaceholder(
            variable_name="agent_scratchpad"
        )
    ]
)


# =========================
# 创建Agent：保持不变
# =========================

agent = create_tool_calling_agent(
    llm,
    tools,
    prompt
)


# =========================
# Agent执行器：保持不变
# =========================

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=10,
    handle_parsing_errors=True,
    return_intermediate_steps=True
)


# =========================
# Redis记忆：保持不变
# =========================

def get_session_history(session_id):

    return RedisMessageHistory(
        session_id
    )



# =========================
# Agent统一入口：保持不变
# =========================


def repair_agent_answer(
    question,
    facility_id,
    original_answer,
    data_context,
    blocking_issues
):
    """
    使用已验证的业务数据修复一次AI回答。
    不重新调用Tool，不写入Redis。
    """

    # 只向模型提供需要修复的风险
    issue_details = [
        {
            "type": item.get("type"),
            "message": item.get("message"),
            "text": item.get("text", "")
        }
        for item in blocking_issues
    ]

    repair_prompt = """
你是黄鳝养殖分析报告的事实核查与修订助手。

下面提供用户问题、原始AI回答、已经查询的业务数据、
以及事实检测发现的风险。

你的任务不是重新查询数据，而是在保留报告分析价值的前提下，
修复原始回答中缺少证据支持的结论。

必须遵守：

1. 只能使用提供的业务数据作为具体养殖池事实。
2. 保留用户要求的分析结构，包括状态、风险和处理建议。
3. 删除或修正未经证实的因果判断。
4. 设备ON/OFF仅代表对应记录时间的状态，
   不得推断连续运行、故障原因或实际停机时长。
5. 不得将单次异常记录直接认定为疾病或传感器故障。
6. 不得编造行业阈值、死亡风险等级或确定性诊断。
   如需使用阈值，只能引用提供的系统配置或可靠依据。
7. 不推荐化学制剂、药物、增氧剂或具体使用剂量。
8. 不得仅凭单次摄食率变化制定确定的停喂天数。
9. 建议优先采用人工复测、设备核查、
   合理机械增氧、现场观察和持续监测。
10. 不确定原因应明确表达证据限制。
    水质氨氮达到0.2 mg/L时属于项目配置的预警范围；
    投喂量单位为kg，摄食率单位为%。
11. 不得编造新的数据、时间、历史事件或工具结果。
12. 直接输出修复后的完整中文报告，
    不要输出修复过程、解释或JSON。
"""

    repair_input = (
        f"养殖池：{facility_id}\n\n"
        f"用户问题：{question}\n\n"
        f"已验证业务数据：\n"
        f"{json.dumps(data_context, ensure_ascii=False, default=str)}\n\n"
        f"检测到的风险：\n"
        f"{json.dumps(issue_details, ensure_ascii=False)}\n\n"
        f"原始AI回答：\n{original_answer}"
    )

    # 使用现有Qwen模型，不经过AgentExecutor
    response = llm.invoke([
        SystemMessage(content=repair_prompt),
        HumanMessage(content=repair_input)
    ])

    repaired_answer = response.content

    if not isinstance(repaired_answer, str):
        raise ValueError("修复回答不是字符串")

    repaired_answer = repaired_answer.strip()

    if not repaired_answer:
        raise ValueError("修复回答为空")

    return repaired_answer




def run_agent(
    question: str,
    facility_id: str,
    session_id: str
):
    start_time = time.perf_counter()
    # 读取Redis历史，暂时不写入
    history = get_session_history(session_id)
    chat_history = history.messages

    # 构造本轮问题
    user_input = (
        f"当前养殖池:\n{facility_id}\n\n"
        f"用户问题:\n{question}"
    )

    # 直接调用AgentExecutor
    perf = PerformanceCallback()

    result = agent_executor.invoke(
        {
            "input": user_input,
            "chat_history": chat_history
        },
        config={
            "callbacks": [perf]
        }
    )

    perf.print_report()
    elapsed = time.perf_counter() - start_time

    print(
        f"[Agent性能] Agent调用耗时: {elapsed:.2f}秒 | "
        f"养殖池: {facility_id} | "
        f"会话: {session_id}"
    )

    # 获取Agent实际执行的工具记录
    intermediate_steps = result.get(
        "intermediate_steps", []
    )

    # 统一检查本轮必要业务Tool结果
    passed, validated_tools, missing_tools, failed_tools = (
        check_required_tool_results(
            question,
            facility_id,
            intermediate_steps
        )
    )

    print(
        f"[Agent执行记录] 工具调用次数: "
        f"{len(intermediate_steps)}"
    )


    # 默认使用Agent原始回答
    final_answer = result["output"]

    if not passed:

        print(
            f"[自动补查] 检测到缺失Tool: "
            f"{sorted(missing_tools)}"
        )

        # 1. 收集Agent本轮已经成功查询的核心业务数据
        verified_data = {}

        core_tools = {
            "query_water_quality",
            "query_feeding_record",
            "query_device_status",
            "query_alarm_history"
        }

        for action, observation in intermediate_steps:

            tool_name = action.tool

            if tool_name not in core_tools:
                continue

            is_valid, reason = validate_tool_result(
                tool_name,
                observation,
                facility_id
            )

            if is_valid:
                verified_data[tool_name] = observation

        # 2. 只补查缺失或无效的必要Tool
        supplemented, supplement_failed = (
            auto_query_missing_tools(
                missing_tools,
                facility_id
            )
        )

        verified_data.update(supplemented)

        # 3. 再次校验必要数据是否齐全
        remaining = (
            get_required_tools(question)
            - set(verified_data.keys())
        )

        if remaining:

            print(
                f"[自动补查失败] 仍缺失: "
                f"{sorted(remaining)}"
            )

            print(
                f"[自动补查失败] 原因: "
                f"{supplement_failed}"
            )

            return {
                "answer": (
                    "本轮必要业务数据查询不完整，"
                    "无法生成可靠的养殖分析结果，"
                    "请稍后重试。"
                ),
                "sources": []
            }

        # 4. 全部补查成功后，重新生成回答
        print(
            "[自动补查] 必要数据齐全，重新生成回答"
        )

        try:
            final_answer = generate_verified_answer(
                question,
                facility_id,
                verified_data
            )

        except Exception as e:

            print(
                "[重新生成失败]",
                repr(e)
            )

            return {
                "answer": (
                    "业务数据已经查询成功，"
                    "但AI分析暂时未能完成，"
                    "请稍后重试。"
                ),
                "sources": []
            }


    # =========================
    # 最终回答事实一致性检测
    # =========================

    # 整理Agent本轮成功查询的数据
    data_context = build_data_context(
        intermediate_steps,
        facility_id
    )

    # 如果发生过自动补查，将补查数据也纳入检测
    if not passed:
        supplemented_steps = [
            (
                SimpleNamespace(tool=tool_name),
                observation
            )
            for tool_name, observation in supplemented.items()
        ]

        supplemented_context = build_data_context(
            supplemented_steps,
            facility_id
        )

        data_context.update(supplemented_context)

    # 检测最终回答
    consistency_issues = check_answer_consistency(
        final_answer,
        data_context
    )

    if consistency_issues:
        print(
            f"[事实一致性] 检测到"
            f"{len(consistency_issues)}项潜在风险"
        )

        for issue in consistency_issues:
            print(
                f"[事实风险] {issue['type']} | "
                f"{issue['message']} | "
                f"{issue.get('text', '')[:100]}"
            )
    else:
        print("[事实一致性] 未检测到规则覆盖范围内的风险")

    # =========================
    # 高风险回答拦截
    # =========================
    blocking_types = {
    "device_duration",
    "feeding_freshness",
    "feeding_duration",
    "cross_time_comparison",
    "causality",
    "sensor_certainty",
    "chemical_advice",
    "threshold_mismatch",
    "empty_answer"
    }

    blocking_issues = [
        issue
        for issue in consistency_issues
        if issue["type"] in blocking_types
    ]

    print(
        f"[事实拦截检查] "
        f"风险数={len(consistency_issues)} | "
        f"需拦截数={len(blocking_issues)}"
    )


    if blocking_issues:

        print(
            f"[事实校验拦截] 检测到"
            f"{len(blocking_issues)}项风险，"
            f"尝试修复回答"
        )

        repair_success = False

        try:
            # 1. 最多调用一次Qwen修复回答
            repair_start = time.perf_counter()

            repaired_answer = repair_agent_answer(
                question=question,
                facility_id=facility_id,
                original_answer=final_answer,
                data_context=data_context,
                blocking_issues=blocking_issues
            )

            repair_elapsed = (
                time.perf_counter() - repair_start
            )

            print(
                f"[回答修复] Qwen修复耗时: "
                f"{repair_elapsed:.2f}秒"
            )

            # 2. 再次执行事实检测
            repaired_issues = check_answer_consistency(
                repaired_answer,
                data_context
            )

            repaired_blocking = [
                issue
                for issue in repaired_issues
                if issue["type"] in blocking_types
            ]

            print(
                f"[修复后校验] "
                f"风险数={len(repaired_issues)} | "
                f"需拦截数={len(repaired_blocking)}"
            )

            # 3. 检测通过则使用修复后的完整报告
            if not repaired_blocking:

                final_answer = repaired_answer
                repair_success = True

                print(
                    "[回答修复成功] "
                    "使用修复后的完整AI回答"
                )

            else:

                for issue in repaired_blocking:
                    print(
                        f"[修复仍有风险] "
                        f"{issue['type']} | "
                        f"{issue.get('text', '')[:100]}"
                    )

        except Exception as e:

            print(
                "[回答修复失败]",
                repr(e)
            )

        # 4. 只有修复失败才执行原有安全降级
        if not repair_success:

            print(
                "[安全降级] 回答未通过修复校验，"
                "使用业务数据生成安全摘要"
            )

            safe_answer = build_safe_fallback_answer(
                data_context
            )

            if not data_context or (
                "缺少可用于生成可靠摘要的业务数据"
                in safe_answer
            ):

                print(
                    "[安全降级失败] "
                    "无可用业务数据，不写入Redis"
                )

                return {
                    "answer": safe_answer,
                    "sources": []
                }

            final_answer = safe_answer

            print(
                "[安全降级成功] "
                "使用经过校验的业务数据摘要"
            )

    # =========================
    # 通过检查才保存Redis
    # =========================
    history.add_message(
        HumanMessage(content=user_input)
    )

    history.add_message(
        AIMessage(content=final_answer)
    )

    print(
        f"[Redis写入] 会话: {session_id} | "
        f"校验通过，保存成功"
    )

    return {
        "answer": final_answer,
        "sources": []
    }

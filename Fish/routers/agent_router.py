from fastapi import APIRouter
from Fish.schemas.agent_schema import ChatRequest
from Fish.agent.agent import run_agent
from Fish.agent.router import classify_question
from Fish.agent.llm import llm
from Fish.tools.rag_tool import query_aquaculture_knowledge
from openai import APITimeoutError
from fastapi import HTTPException

from langchain_core.messages import (
    SystemMessage,
    HumanMessage
)

router = APIRouter(
    prefix="/agent",
    tags=["Agent"]
)


# =========================
# 多轮追问识别
# =========================

FOLLOWUP_KEYWORDS = [
    "它",
    "这个池",
    "该池",
    "刚才",
    "上述",
    "前面说的",
    "这些异常",
    "这些风险",
    "先处理什么",
    "还有其他风险",
    "严重吗"
]


def is_farming_followup(question: str) -> bool:
    """
    判断是否可能属于养殖业务追问。
    这里只做最小关键词兜底。
    """

    return any(
        keyword in question
        for keyword in FOLLOWUP_KEYWORDS
    )


# =========================
# 统一回答格式
# =========================

def normalize_result(result):
    """
    统一输出：
    {
        "answer": str,
        "sources": list
    }
    """

    sources = []

    # Agent/RAG返回字典
    if isinstance(result, dict):

        sources = result.get("sources", [])

        answer = result.get(
            "answer",
            result.get("content", "")
        )

        # 兼容嵌套对象
        for _ in range(3):

            if not isinstance(answer, dict):
                break

            nested_sources = answer.get("sources", [])

            if not sources and isinstance(
                nested_sources, list
            ):
                sources = nested_sources

            answer = answer.get(
                "answer",
                answer.get("content", "")
            )

    elif isinstance(result, str):

        answer = result

    else:

        # 兼容AIMessage等对象
        answer = getattr(
            result,
            "content",
            ""
        )

    if not isinstance(answer, str):
        answer = str(answer)

    if not isinstance(sources, list):
        sources = []

    return {
        "answer": answer,
        "sources": sources
    }


# =========================
# Agent聊天接口
# =========================

def generate_rag_answer(question: str) -> dict:
    """
    FAISS检索 + Qwen回答 + 来源返回
    """

    # 1. 检索知识库
    result = query_aquaculture_knowledge.invoke(
        {"question": question}
    )

    # 2. 提取检索内容与来源
    if not isinstance(result, dict):
        return {
            "answer": "知识库返回格式异常。",
            "sources": []
        }

    content = result.get("content", "")
    sources = result.get("sources", [])

    if not isinstance(content, str):
        content = ""

    if not isinstance(sources, list):
        sources = []

    if not content.strip() or content == "未找到相关养殖知识":
        return {
            "answer": "当前知识库未检索到足够的相关资料，无法可靠回答。",
            "sources": []
        }

    # 3. Qwen生成回答
    messages = [
        SystemMessage(
            content="""
        你是黄鳝养殖专业知识问答助手。

        请严格依据提供的FAISS知识片段回答。

        【回答规则】

        1. 优先直接回答用户问题。
        2. 简单知识问题控制在80～150字左右。
        3. 处理方法类问题可以使用3～5条建议。
        4. 不主动生成完整养殖分析报告。
        5. 不引用Redis历史中的养殖池数据。
        6. 用户没有明确询问具体养殖池时，
           不得加入A001等养殖池的监测数值。
        7. 不得编造知识片段之外的技术参数。
        8. 不得擅自推荐药剂、药物及使用剂量。
        9. 知识库没有支持的内容应说明依据不足。
        10. 不得把一般养殖知识说成实时监测结果。

        【回答格式】

        直接给出结论。
        必要时简要列出原因或处理措施。
        避免重复、夸张和无关内容。
        """
        ),
        HumanMessage(
            content=(
                f"用户问题：\n{question}\n\n"
                f"检索到的知识片段：\n{content}\n\n"
                "请根据以上内容回答。"
            )
        )
    ]

    response = llm.invoke(messages)

    answer = response.content

    if not isinstance(answer, str):
        answer = str(answer)

    return {
        "answer": answer,
        "sources": sources
    }



@router.post("/chat")
def chat(req: ChatRequest):

    try:

        # 原有问题分类
        question_type = classify_question(
            req.question
        )

        # 多轮追问优先交给带记忆的Agent
        if (
            question_type == "chat"
            and is_farming_followup(req.question)
        ):
            question_type = "database"

        print(
            f"[Router] 问题: {req.question} | "
            f"分类: {question_type} | "
            f"养殖池: {req.facility_id} | "
            f"会话: {req.session_id}"
        )

        # 数据库与多轮业务追问
        if question_type == "database":

            result = run_agent(
                req.question,
                req.facility_id,
                req.session_id
            )

        # RAG知识库
        elif question_type == "rag":

            print("[RAG] 开始检索知识库")

            result = generate_rag_answer(
                req.question
            )

            print(
                "[RAG] 回答生成完成，来源：",
                result.get("sources", [])
            )
        # 普通聊天
        else:

            result = llm.invoke(
                req.question
            )

        # 统一转换后返回
        return normalize_result(result)


    except APITimeoutError as e:

        print("[Qwen超时]", repr(e))

        raise HTTPException(

            status_code=504,

            detail="Qwen模型请求超时，请稍后重试。"

        )


    except Exception as e:

        print("[Agent错误]", repr(e))

        raise HTTPException(

            status_code=500,

            detail="Agent运行异常，请查看后端日志。"

        )
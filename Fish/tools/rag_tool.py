
from langchain_core.tools import tool

from Fish.rag.retriever import search_knowledge


@tool
def query_aquaculture_knowledge(
    question: str
):
    """
    查询黄鳝养殖知识库。

    返回检索内容及真实文档来源。
    """

    docs = search_knowledge(question)

    if not docs:
        return {
            "content": "未找到相关养殖知识",
            "sources": []
        }

    contents = []
    sources = []

    for doc in docs:

        content = doc.get("content", "")
        source = doc.get("source")

        if content:
            contents.append(content)

        # 只收集实际存在的来源
        if source and source not in sources:
            sources.append(source)

    return {
        "content": "\n\n".join(contents),
        "sources": sources
    }
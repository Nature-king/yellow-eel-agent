from langchain_huggingface import HuggingFaceEmbeddings

from langchain_community.vectorstores import FAISS

from pathlib import Path



# =========================
# 加载Embedding模型
# =========================


BASE_DIR = Path(__file__).resolve().parent


embeddings = HuggingFaceEmbeddings(

    model_name="BAAI/bge-small-zh-v1.5",

    model_kwargs={
        "device":"cpu"
    },

    encode_kwargs={
        "normalize_embeddings":True
    }

)



# =========================
# 加载FAISS
# =========================


vector_path = (

    BASE_DIR

    /

    "vector_db"

)



vector_store = FAISS.load_local(

    str(vector_path),

    embeddings,

    allow_dangerous_deserialization=True

)



# =========================
# 创建检索器
# =========================


retriever = vector_store.as_retriever(

    search_kwargs={

        "k":3

    }

)




def search_knowledge(query: str):
    """
    检索黄鳝养殖知识。

    返回：
    [
        {
            "content": "知识片段",
            "source": "文档来源",
            "chunk_id": "片段编号"
        }
    ]
    """

    docs = retriever.invoke(query)

    result = []

    for doc in docs:

        metadata = doc.metadata or {}

        source = metadata.get("source")

        if source:
            source = str(source)
        else:
            source = None

        result.append({
            "content": doc.page_content,
            "source": source,
            "chunk_id": metadata.get(
                "chunk_id"
            )
        })

    return result
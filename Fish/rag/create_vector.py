from langchain_community.document_loaders import TextLoader

from langchain.text_splitter import RecursiveCharacterTextSplitter
from pathlib import Path
from langchain_community.vectorstores import FAISS

from langchain_community.embeddings import HuggingFaceBgeEmbeddings

from dotenv import load_dotenv

import os



load_dotenv()



# ======================
# 读取知识文档
# ======================

# 当前create_vector.py所在目录
BASE_DIR = Path(__file__).resolve().parent


# documents/eel_knowledge.txt
knowledge_file = (
    BASE_DIR
    /
    "documents"
    /
    "eel_knowledge.txt"
)


loader = TextLoader(
    str(knowledge_file),
    encoding="utf-8"
)


documents = loader.load()



# ======================
# 文档切分
# ======================


splitter = RecursiveCharacterTextSplitter(

    chunk_size=300,

    chunk_overlap=50

)


docs = splitter.split_documents(
    documents
)



# ======================
# 创建Embedding
# ======================


embeddings = HuggingFaceBgeEmbeddings(

    model_name=
    "BAAI/bge-small-zh-v1.5",

    model_kwargs={
        "device":"cpu"
    },

    encode_kwargs={
        "normalize_embeddings":True
    }

)


# ======================
# 创建FAISS
# ======================


vector_store = FAISS.from_documents(

    docs,

    embeddings

)



# 保存

vector_store.save_local(

    "Fish/rag/vector_db"

)


print(
    "知识库创建完成"
)
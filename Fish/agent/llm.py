from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
import os


load_dotenv()


llm = ChatOpenAI(
    model=os.getenv("QWEN_MODEL", "qwen3.7-flash-2026-07-15"),
    api_key=os.getenv("DASHSCOPE_API_KEY"),
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    temperature=float(os.getenv("TEMPERATURE", 0.2)),
    timeout=300,
    max_retries=1
)
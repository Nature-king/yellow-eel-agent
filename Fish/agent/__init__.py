from dotenv import load_dotenv

from langchain_openai import ChatOpenAI


import os



# 加载.env

load_dotenv()



# 创建Qwen模型


llm = ChatOpenAI(

    model="qwen-plus",

    api_key=os.getenv(
        "DASHSCOPE_API_KEY"
    ),

    base_url=
    "https://dashscope.aliyuncs.com/compatible-mode/v1",

    temperature=0.2

)
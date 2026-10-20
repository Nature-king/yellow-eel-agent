from pydantic import BaseModel



class AgentRequest(BaseModel):

    """
    Agent请求
    """

    query:str

    # 对话ID
    session_id:str="default"




class AgentResponse(BaseModel):

    """
    Agent响应
    """

    answer:str


class ChatRequest(BaseModel):

    question:str
    session_id:str
    facility_id:str

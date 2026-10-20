from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware


from Fish.routers.agent_router import router as agent_router
from Fish.routers.farm_router import router as farm_router



app = FastAPI(

    title="Yellow Eel Agent",

    description="智慧鳝养AI养殖系统",

    version="1.0"

)



# 跨域

app.add_middleware(

    CORSMiddleware,

    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],

    allow_credentials=True,

    allow_methods=["*"],

    allow_headers=["*"]

)



# Agent接口

app.include_router(agent_router)


# 养殖数据接口

app.include_router(farm_router)



@app.get("/")
def root():

    return {

        "message":
        "智慧鳝养 Agent Running"

    }
"""python -m autotrade.api 启动 Web API 服务器。"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("autotrade.api.server:app", host="0.0.0.0", port=8080, reload=True)

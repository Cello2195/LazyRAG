import lazyllm
from lazyllm.tools.agent import ReactAgent
from lazyllm.tools import MCPClient

mcp_configs = {
    "amap_mcp": {
        "url": "http://mcp.amap.com/sse?key=428ccf77c9748a131f2ea422aa06ebac"
    }
}

client = MCPClient(command_or_url=mcp_configs["amap_mcp"]["url"])
llm = lazyllm.OnlineChatModule(source='qwen', model='qwen-max-latest', stream=False)
agent = ReactAgent(llm=llm.share(), tools=client.get_tools(), max_retries=15)
print(agent("查询北京市的天气"))

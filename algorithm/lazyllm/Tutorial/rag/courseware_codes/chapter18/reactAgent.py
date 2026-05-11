import lazyllm
from lazyllm.tools import fc_register, ReactAgent
@fc_register("tool")
def multiply_tool(a: int, b: int) -> int:
    '''
    Multiply two integers and return the result integer

    Args:
        a (int): multiplier
        b (int): multiplier
    '''
    return a * b

@fc_register("tool")
def add_tool(a: int, b: int):
    '''
    Add two integers and returns the result integer

    Args:
        a (int): addend
        b (int): addend
    '''
    return a + b
tools = ["multiply_tool", "add_tool"]
# llm = lazyllm.TrainableModule("internlm2-chat-20b").start()   # or llm = lazyllm.OnlineChatModule()
llm = lazyllm.OnlineChatModule(source='qwen',model='qwen-max-latest',stream=False)
agent = ReactAgent(llm, tools)
query = "What is 20+(2*4)? Calculate step by step."
res = agent(query)
print(res)
# 'Answer: The result of 20+(2*4) is 28.'

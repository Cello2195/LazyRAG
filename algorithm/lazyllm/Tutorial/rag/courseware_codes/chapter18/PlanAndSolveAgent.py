import lazyllm
from lazyllm.tools import fc_register, PlanAndSolveAgent

@fc_register("tool")
def multiply(a: int, b: int) -> int:
    """
    Multiply two integers and return the result integer

    Args:
        a (int): multiplier
        b (int): multiplier
    """
    return a * b

@fc_register("tool")
def add(a: int, b: int):
    """
    Add two integers and returns the result integer

    Args:
        a (int): addend
        b (int): addend
    """
    return a + b

tools = ["multiply", "add"]
# llm = lazyllm.TrainableModule("internlm2-chat-20b").start()   # or llm = lazyllm.OnlineChatModule()
llm = lazyllm.OnlineChatModule(source='qwen',model='qwen-max-latest',stream=False)

agent = PlanAndSolveAgent(llm, tools=tools)
query = "What is 20+(2*4)? Calculate step by step."
ret = agent(query)
print(ret)
# The final answer is 28.

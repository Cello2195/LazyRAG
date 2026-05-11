import os
from lightrag import LightRAG
from lightrag.llm.openai import openai_complete, openai_embed
from lightrag.utils import EmbeddingFunc

WORKING_DIR = "****"
PATH_TO_TXT = "path/to/your/data"

if not os.path.exists(WORKING_DIR):
    os.makedirs(WORKING_DIR)

api_key = "empty"

rag = LightRAG(
    working_dir=WORKING_DIR,
    llm_model_func=openai_complete,
    llm_model_name="qwen2",
    llm_model_kwargs={"base_url":"http://0.0.0.0:12345/v1", "api_key":api_key},
    embedding_func=EmbeddingFunc(
        embedding_dim=1024,
        max_token_size=8192,
        func=lambda texts: openai_embed(
            texts=texts,
            model="bge-large",
            base_url="http://127.0.0.1:19001", 
            api_key=api_key,
        )
    ),
)

with open(PATH_TO_TXT, "r", encoding="utf-8") as f:
    rag.insert(f.read())

import os
from cerebras.cloud.sdk import Cerebras

client = Cerebras(
    api_key=os.getenv("CEREBRAS_API_KEY")
)

MODEL_NAME = "llama3.1-8b"


SYSTEM_PROMPT = """
You are a physics mentor guiding a student step by step.

Rules:
- Do NOT give the full solution.
- Break problems into micro steps.
- Ask guiding questions.
- Encourage thinking.
- Keep replies short (3-6 lines).
- Sound natural and collaborative.
"""


def call_free_model(conversation):

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=0.6,
        max_tokens=400
    )

    return response.choices[0].message.content
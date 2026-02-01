import base64
import requests
import os
import json

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL = "mistralai/pixtral-12b"


def encode_image(path):
    response = requests.get(url, timeout=15)
    response.raise_for_status()  # raise error if download fails
    return base64.b64encode(response.content).decode()


def verify_image_answer(question_text, answer_text, image_path, domain):
    image_b64 = encode_image(image_path)

    prompt = f"""
    You are an expert grader in {domain}.

    TASK:
    Verify whether the IMAGE contains a correct solution to the QUESTION.
    The image is NOT illustrative — it is the PRIMARY solution.

    QUESTION:
    {question_text}

    OPTIONAL TEXT BY USER:
    {answer_text}

    INSTRUCTIONS:
    - Extract equations, diagrams, reasoning from the image.
    - Check correctness, assumptions, and final conclusion.
    - Penalize conceptual or mathematical errors.
    - Ignore handwriting quality.

    OUTPUT JSON ONLY:
    {{
      "score": 0.0 to 1.0,
      "reasoning": "short explanation",
      "audit": "key issues or confirmation"
    }}
    """

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{image_b64}"
                        }
                    }
                ]
            }
        ],
        "response_format": {"type": "json_object"}
    }

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers=headers,
        json=payload,
        timeout=60
    )

    raw_content = response.json()["choices"][0]["message"]["content"]

    try:
        clean_json = raw_content.replace("```json", "").replace("```", "").strip()

        return json.loads(clean_json)
    
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "score": 0.0, "reasoning": "AI service not available", "audit": "AI service not available"

        }

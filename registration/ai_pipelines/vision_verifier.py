import base64
import requests
import os
import json

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
# MODEL = "mistralai/pixtral-12b"
MODEL = "meta-llama/llama-3.2-11b-vision-instruct"


def encode_image(url):
    response = requests.get(url, timeout=15)
    response.raise_for_status()  # raise error if download fails
    return base64.b64encode(response.content).decode()


def verify_image_answer(question_text, answer_text, image_path_a, image_path_q, domain):

    try:
        content_blocks = []
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

        OUTPUT JSON ONLY EXACTLY IN THIS FORMAT:
        {{
        "score": 0.0 to 1.0,
        "reasoning": "short explanation",
        "audit": "key issues or confirmation"
        }}
        You are a grading engine.

        You are NOT allowed to answer the question.
        You must ONLY evaluate the given answer.

        If you answer the question directly, that is a failure.

        Return ONLY a valid JSON object.
        Do NOT include explanations before or after.
        Do NOT use markdown.
        """
        content_blocks.append({
            "type": "text",
            "text": prompt
        })

        # Add question image if present
        if image_path_q:
            image_b64_q = encode_image(image_path_q)
            content_blocks.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_b64_q}"
                }
            })

        # Add answer image if present
        if image_path_a:
            image_b64_a = encode_image(image_path_a)
            content_blocks.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_b64_a}"
                }
            })
        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": content_blocks,
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0
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

        # raw_content = response.json()["choices"][0]["message"]["content"]
        response_json = response.json()

        print("FULL RESPONSE:", response_json)  # TEMP DEBUG

        if "choices" not in response_json:
            return {
                "score": 0.0,
                "reasoning": "AI error",
                "audit": str(response_json)
            }

        raw_content = response_json["choices"][0]["message"]["content"]
        # clean_json = raw_content.replace("```json", "").replace("```", "").strip()
        import re

        raw_content = response_json["choices"][0]["message"]["content"]

        # Extract first JSON object from text
        json_match = re.search(r"\{.*\}", raw_content, re.DOTALL)

        if not json_match:
            return {
                "score": 0.0,
                "reasoning": "Invalid AI format",
                "audit": raw_content
            }

        clean_json = json_match.group(0)

        return json.loads(clean_json)

        # return json.loads(clean_json)
    
    except Exception as e:
        import traceback
        print("VISION ERROR:")
        traceback.print_exc()
        return {
            "score": 0.0, "reasoning": "AI service not available", "audit": str(e)

        }


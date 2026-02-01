import json
from cerebras.cloud.sdk import Cerebras
import os
from dotenv import load_dotenv

load_dotenv()

SMART_MODEL = "llama-3.3-70b"
FAST_MODEL = "llama3.1-8b"

client = Cerebras(api_key=os.getenv("CEREBRAS_API_KEY"))

def call_llm(prompt, system_prompt, model, json_mode=False):
    """
    Wrapper for Cerebras API calls.
    Handles JSON formatting and temperature settings automatically.
    """
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            # Use 0.0 for strict logic (Solver), 0.2 for creative formatting (Critic)
            temperature=0.2 if json_mode else 0.0,
            # Cerebras specific parameter for JSON enforcement
            response_format={"type": "json_object"} if json_mode else None
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Error: {str(e)}"
    
# --- THE SOLVER (Llama 3.3 70B) ---
def solver(question, domain):

    system = f"""
    You are an expert World-Class professional in {domain}.
    Your task: Solve the user's problem, accurately and concisely, using modern best practices.
    1. Rely ONLY on your internal knowledge.
    2. Do NOT look at any provided answers (you are generating the ground truth).
    3. Be concise and provide code/steps if applicable. If the question is subjective, provide the most generally accepted academic view.
    """

    return call_llm(question, system, SMART_MODEL)

# --- THE COMPARATOR (Llama 3.3 70B) ---
def comparator(question, reference, target):

    system = """
    You are a Meticulous Technical Auditor.
    Compare the 'Reference Solution' vs 'Candidate Answer'.
    Your goal is to identify if the candidate is functionally equivalent to the reference.

    INSTRUCTIONS:
    1. If the Candidate Answer conveys the EXACT SAME meaning/logic as the Reference (even if wording differs), output: "NO SEMANTIC DIFFERENCES."
    2. If there are distinct logical errors or missing facts, list them as bullet points.
    3. Ignore tone, formatting, or variable naming.
    4. If the Candidate Answer uses a DIFFERENT but VALID approach, note that explicitly.
    """

    user_input = f"""
    [QUESTION]: {question}

    [REFERENCE SOLUTION]:
    {reference}

    [CANDIDATE ANSWER]:
    {target}
    """

    return call_llm(user_input, system, SMART_MODEL)

# --- AGENT 3: THE CRITIC (Llama 3.1 8B) ---
def critic(question, comparison, target):

    system = """ You are an Expert Domain Grader. Rate the 'Candidate Answer' based strictly on the 'Audit Report' (Reference Answer).

      INSTRUCTIONS:
      1. Prioritize MEANING over wording. If the Candidate Answer conveys the correct scientific concept and outcome, it should be scored highly, even if phrased differently.
      2. Ignore minor stylistic differences or extra context unless it contradicts the truth.
      3. Identify the "Core Facts" in the Reference Key.
      4. Check if those Core Facts exist in the Candidate Answer.
      5. Ignore grammar, tone, or sentence structure unless it confuses the meaning.
      6. Use the following CONTINUOUS SCALE (0.0 to 1.0):

      ANCHORS:
      - 1.0 (Perfect): The Audit Report states "NO SEMANTIC DIFFERENCES" or confirms the answer is valid/equivalent.
      - 0.8 (Verified): The answer is correct but the Audit Report highlights minor omissions or lack of specific terminology that does not affect the correctness.
      - 0.5 (Partial): Audit Report lists missing core concepts.
      - 0.0 (Wrong): Dangerous or Incorrect.

      OUTPUT FORMAT (JSON ONLY):
      {
        "score": <float>,
        "reasoning": "<concise explanation focusing on factual accuracy>"
      }
      """

    user_input = f"""
    [QUESTION]: {question}
    [CANDIDATE ANSWER]: {target}
    [AUDIT REPORT]: {comparison}
    """

    # Force valid JSON output
    return call_llm(user_input, system, FAST_MODEL, json_mode=True)

# --- MAIN WORKFLOW ---
def verify_answer(question: str, answer_text: str, domain: str):

    # Step 1: Solver
    reference_sol = solver(question, domain)

    # Step 2: Comparator (Audit)
    diffs = comparator(question, reference_sol, answer_text)

    # Step 3: Critic (Score)
    verdict_json = critic(question, diffs, answer_text)

    try:
        result = json.loads(verdict_json)
        return {
            "score": float(result.get("score", 0.0)),
            "reasoning": result.get("reasoning", ""),
            "audit": diffs,
            "verified": result["score"] >= 0.6
        }

    except json.JSONDecodeError:
        return {
            "score": 0.0,
            "reasoning": "AI verification failed due to malformed response.",
            "audit": verdict_json,
            "verified": 0
        }



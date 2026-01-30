from .ai_verifier import verify_answer as text_verify
from .vision_verifier import verify_image_answer

def run_ai_verification(answer):
    try:
        has_text = bool(answer.body and answer.body.strip())
        has_image = bool(answer.image)
        domain = derive_domain_from_tags(answer.question.tags)

        if has_image:
            result = verify_image_answer(
                answer.question.body,
                answer.body or '',
                answer.image.path,
                domain
            )
        else:
            result = text_verify(answer.question.body, answer.body, domain)

        answer.ai_score = result.get('score')
        answer.ai_reasoning = result.get('reasoning')
        answer.ai_audit = result.get('audit', '')
        answer.save(update_fields=['ai_score', 'ai_reasoning', 'ai_audit'])

    except:
        answer.ai_reasoning = 'AI assessment unavailable'
        answer.save(update_fields=['ai_reasoning'])

def derive_domain_from_tags(tags):
    """
    Converts tags like 'Physics, Quantum Mechanics'
    into a domain string usable by the AI.
    """
    if not tags:
        return "General"

    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    return ", ".join(tag_list[:3])  # limit to top 3
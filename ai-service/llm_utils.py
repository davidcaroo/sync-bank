import json
import re

def extract_json_object(text: str) -> dict:
    content = (text or "").strip()
    if not content:
        raise ValueError("Respuesta vacia del modelo")

    if "```json" in content:
        content = content.split("```json", 1)[1].split("```", 1)[0].strip()
    elif "```" in content:
        content = content.split("```", 1)[1].split("```", 1)[0].strip()

    try:
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        raise ValueError("No se encontro JSON en la respuesta del modelo")

    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("El JSON de respuesta no es un objeto")
    return parsed

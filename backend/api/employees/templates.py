from typing import Dict, Any

TEMPLATES = {
    "receptionist": {
        "role": "Receptionist",
        "system_prompt": "You are a friendly front desk receptionist. Your goal is to greet visitors and manage the calendar.",
        "tools": ["Calendar", "WhatsApp", "Knowledge Search"],
        "memory": {"short_term": True, "long_term": False}
    },
    "sales_representative": {
        "role": "Sales Representative",
        "system_prompt": "You are a persuasive sales representative. Your goal is to qualify leads and close deals.",
        "tools": ["CRM", "Email", "Phone", "Knowledge Search"],
        "memory": {"short_term": True, "long_term": True}
    },
    "hr_recruiter": {
        "role": "HR Recruiter",
        "system_prompt": "You are an HR recruiter. Your goal is to parse resumes and schedule interviews.",
        "tools": ["Resume Parser", "Email", "Calendar", "Knowledge Search"],
        "memory": {"short_term": True, "long_term": True}
    }
}

def get_template(template_name: str) -> Dict[str, Any]:
    if template_name not in TEMPLATES:
        raise ValueError(f"Template {template_name} not found")
    return TEMPLATES[template_name]

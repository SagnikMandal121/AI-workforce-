import os

def replace_in_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    new_content = content
    for old, new in replacements:
        new_content = new_content.replace(old, new)
        
    if new_content != content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {filepath}")

replacements = [
    ("database.", "database."),
    ("database.models.employee", "database.models.employee"),
    ("database.repositories.employee_repository", "database.repositories.employee_repository"),
    ("backend.services.employee_service", "backend.services.employee_service"),
    ("backend.api.employees.router", "backend.api.employees.router"),
    ("backend.api.employees.templates", "backend.api.employees.templates"),
    ("backend.api.employees", "backend.api.employees"), # catch all remaining
    ("backend.api.employees", "backend.api.employees"),
    ("backend.api.auth", "backend.api.auth"),
    ("backend.api.conversations", "backend.api.conversations"),
    ("backend.api.knowledge", "backend.api.knowledge"),
    ("database.base", "database.base") # fix base.py import in employee models
]

for root, _, files in os.walk('.'):
    if '.git' in root or '.venv' in root or '__pycache__' in root:
        continue
    for file in files:
        if file.endswith('.py'):
            filepath = os.path.join(root, file)
            replace_in_file(filepath, replacements)

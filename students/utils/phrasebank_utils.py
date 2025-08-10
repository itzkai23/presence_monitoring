import csv
import random

PHRASEBANK_PATH = "students/phrasebank/summary_phrases.csv"

def load_phrasebank(filepath=PHRASEBANK_PATH):
    bank = {}
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            bank.setdefault(row["category"], []).append(row["template"])
    return bank

def choose_phrase(category, data=None, phrasebank=None):
    if phrasebank is None:
        phrasebank = load_phrasebank()
    templates = phrasebank.get(category, [])
    if not templates:
        return ""
    template = random.choice(templates)
    return template.format(**(data or {}))

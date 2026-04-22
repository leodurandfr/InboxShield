"""Quick verification that all Session 2 services import and work correctly."""

# Encryption
from app.services.encryption import encrypt, decrypt
print("encryption OK")

# IMAP Service
from app.services.imap_service import (
    detect_provider, test_connection, fetch_new_emails, fetch_recent_emails,
    move_email, set_flag, create_folder, clean_body, FetchedEmail, ConnectionTestResult,
    PROVIDER_MAP,
)
print(f"imap_service OK — {len(PROVIDER_MAP)} providers mapped")

info = detect_provider("leo@gmx.fr")
print(f"  detect_provider(leo@gmx.fr) = {info.provider}, {info.host}:{info.port}")
info2 = detect_provider("user@gmail.com")
print(f"  detect_provider(user@gmail.com) = {info2.provider}, {info2.host}:{info2.port}")
unknown = detect_provider("user@custom.org")
print(f"  detect_provider(user@custom.org) = {unknown}")

html = "<html><body><p>Hello world!</p><p>Content here.</p><div>-- <br>Signature</div></body></html>"
cleaned = clean_body(html, None, max_length=100)
print(f'  clean_body = "{cleaned}"')

# LLM
from app.llm.base import BaseLLMProvider, ClassificationResult
from app.llm.ollama import OllamaProvider
from app.llm.prompts import build_classification_prompt, build_rule_interpretation_prompt
print("llm base/ollama/prompts OK")

# LLM Service
from app.services.llm_service import (
    classify_email, interpret_rule, create_provider,
    parse_classification_json, parse_rule_json, VALID_CATEGORIES,
)
print(f"llm_service OK — {len(VALID_CATEGORIES)} categories")

# Test JSON parsing - clean
test1 = parse_classification_json(
    '{"category": "newsletter", "confidence": 0.9, "explanation": "test", "is_spam": false, "is_phishing": false, "phishing_reasons": []}'
)
assert test1 is not None
print(f"  parse clean JSON: category={test1['category']}, confidence={test1['confidence']}")

# Test JSON parsing - markdown wrapped
test2 = parse_classification_json(
    'Here is the result:\n```json\n{"category": "spam", "confidence": 0.85, "explanation": "unsolicited", "is_spam": true, "is_phishing": false, "phishing_reasons": []}\n```'
)
assert test2 is not None
print(f"  parse markdown-wrapped JSON: category={test2['category']}")

# Test JSON parsing - partial
test3 = parse_classification_json(
    'I think this is a promotion email. {"category": "promotion", "confidence": 0.7}'
)
assert test3 is not None
print(f"  parse partial JSON: category={test3['category']}")

# Test JSON parsing - rule
rule_test = parse_rule_json('{"matches": true, "reason": "test match"}')
assert rule_test is not None
print(f"  parse rule JSON: matches={rule_test['matches']}")

# Test provider factory
provider = create_provider("ollama", "qwen2.5:7b", "http://localhost:11434")
print(f"  create_provider(ollama) = {type(provider).__name__}, model={provider.get_model_name()}")

print()
print("ALL IMPORTS AND TESTS PASSED")

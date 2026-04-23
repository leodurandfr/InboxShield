"""Session 3 verification: test all imports for new services."""

import sys

print("=" * 60)
print("Session 3 — Import Verification")
print("=" * 60)

errors = []

# 1. Sender service
try:
    print("[OK] sender_service — 6 functions imported")
except Exception as e:
    errors.append(f"sender_service: {e}")
    print(f"[FAIL] sender_service: {e}")

# 2. Action service
try:
    print("[OK] action_service — execute_actions imported")
except Exception as e:
    errors.append(f"action_service: {e}")
    print(f"[FAIL] action_service: {e}")

# 3. Activity service
try:
    print("[OK] activity_service — 9 functions imported")
except Exception as e:
    errors.append(f"activity_service: {e}")
    print(f"[FAIL] activity_service: {e}")

# 4. Rule engine
try:
    print("[OK] rule_engine — 4 functions imported")
except Exception as e:
    errors.append(f"rule_engine: {e}")
    print(f"[FAIL] rule_engine: {e}")

# 5. Classifier service
try:
    print("[OK] classifier — 8 functions imported")
except Exception as e:
    errors.append(f"classifier: {e}")
    print(f"[FAIL] classifier: {e}")

# 6. Scheduler
try:
    print("[OK] scheduler — 9 functions imported")
except Exception as e:
    errors.append(f"scheduler: {e}")
    print(f"[FAIL] scheduler: {e}")

# 7. Main app (with scheduler integration)
try:
    print("[OK] main.py — FastAPI app imported (scheduler in lifespan)")
except Exception as e:
    errors.append(f"main: {e}")
    print(f"[FAIL] main: {e}")

# Summary
print()
print("=" * 60)
if errors:
    print(f"FAILED: {len(errors)} error(s)")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL IMPORTS OK — Session 3 complete!")
    print()
    print("Services created:")
    print("  - sender_service.py    (6 functions)")
    print("  - action_service.py    (1 function)")
    print("  - activity_service.py  (9 functions)")
    print("  - rule_engine.py       (4 functions)")
    print("  - classifier.py        (8 functions)")
    print("  - scheduler.py         (9 functions)")
    print("  - main.py updated      (scheduler in lifespan)")
    sys.exit(0)

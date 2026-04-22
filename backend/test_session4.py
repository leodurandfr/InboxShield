"""Session 4 verification: test all API router imports and route count."""

import sys

print("=" * 60)
print("Session 4 — API Endpoints Verification")
print("=" * 60)

errors = []

# 1. Import all API modules
modules = {
    "accounts": "app.api.accounts",
    "emails": "app.api.emails",
    "review": "app.api.review",
    "rules": "app.api.rules",
    "activity": "app.api.activity",
    "settings": "app.api.settings",
    "system": "app.api.system",
}

for name, module_path in modules.items():
    try:
        mod = __import__(module_path, fromlist=["router"])
        router = getattr(mod, "router")
        route_count = len(router.routes)
        print(f"[OK] {name:12s} — {route_count} routes")
    except Exception as e:
        errors.append(f"{name}: {e}")
        print(f"[FAIL] {name}: {e}")

# 2. Import main app and check all routes are mounted
print()
try:
    from app.main import app

    all_routes = []
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            for method in route.methods:
                if method in ("GET", "POST", "PUT", "DELETE"):
                    all_routes.append(f"{method:6s} {route.path}")

    print(f"FastAPI app loaded — {len(all_routes)} API routes total:")
    for r in sorted(all_routes):
        print(f"  {r}")

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
    print("ALL API ROUTES LOADED — Session 4 complete!")
    sys.exit(0)

import asyncio, sys
sys.path.insert(0, '.')

async def main():
    print("=== HR Policy RAG - End-to-End Demo ===\n")

    # Test 1: Auth - JWT creation and validation
    from src.auth import create_test_token, validate_token, ROLE_CLEARANCE_MAP
    token = create_test_token(user_id="emp-001", role="employee")
    print(f"JWT Token created (employee role)")
    # validate_token is synchronous (FastAPI Depends function)
    user = validate_token(f"Bearer {token}")
    print(f"  User ID: {user.user_id}, Clearance: {user.clearance_level}")

    token_mgr = create_test_token(user_id="user-002", role="manager")
    user_mgr = validate_token(f"Bearer {token_mgr}")
    print(f"  Manager: {user_mgr.user_id}, Clearance: {user_mgr.clearance_level}")

    token_hr = create_test_token(user_id="user-003", role="hr_admin")
    user_hr = validate_token(f"Bearer {token_hr}")
    print(f"  HR Admin: {user_hr.user_id}, Clearance: {user_hr.clearance_level}")

    # Test 2: Chunker
    from indexer.chunker import RecursiveChunker
    chunker = RecursiveChunker(chunk_size=500, chunk_overlap=50)

    sample_policy = """# Parental Leave Policy

## Overview
Contoso offers comprehensive parental leave for all eligible employees.

## Eligibility
Employees who have completed 6 months of continuous service are eligible for parental leave.

## Leave Entitlement
- Primary carer: 26 weeks paid leave at 100% salary
- Secondary carer: 4 weeks paid leave at 100% salary
- Adoption leave mirrors maternity leave provisions

## How to Apply
Submit the parental leave request form to HR at least 15 weeks before the expected birth date.
Provide official documentation (birth certificate or adoption order) within 28 days.
"""
    chunks = chunker.chunk(sample_policy, source_file="parental_leave_policy.md", title="Parental Leave Policy", clearance_level=1)
    print(f"\nChunker: split HR policy into {len(chunks)} chunks")
    if chunks:
        print(f"  First chunk: {chunks[0].content[:100]}...")

    # Test 3: Read actual policy documents
    import os
    docs_path = "indexer/documents"
    if os.path.exists(docs_path):
        docs = os.listdir(docs_path)
        print(f"\nPolicy documents available: {len(docs)} files")
        for d in docs:
            print(f"  - {d}")
    else:
        print(f"\nNo indexer/documents directory found (expected in production)")

    # Test 4: RBAC clearance levels
    print(f"\nRBAC clearance levels:")
    for role, level in ROLE_CLEARANCE_MAP.items():
        print(f"  {role}: clearance level {level}")

    print("\n=== HR Policy RAG: Auth, RBAC, and document chunking working ===")

asyncio.run(main())

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Force deterministic, offline test configuration regardless of any local
# .env file -- tests must never depend on network access or real secrets.
os.environ["LEASELENS_LLM_PROVIDER"] = "mock"
os.environ["LEASELENS_ENVIRONMENT"] = "test"
os.environ["LEASELENS_SECRET_KEY"] = "test-secret-key-not-for-production"
os.environ["LEASELENS_DATABASE_URL"] = "sqlite:///:memory:"
os.environ["LEASELENS_RATE_LIMIT_REQUESTS"] = "1000"  # avoid flaky 429s across a fast test run

import pytest

SAMPLE_LEASE = """
RESIDENTIAL LEASE AGREEMENT

This lease is entered into between the Landlord and Tenant for the premises
located in the State of California.

1. RENT. Tenant agrees to pay $2,400 per month. Rent is due on the 1st of
each month. A late fee of $75 applies after a 3-day grace period.

2. SECURITY DEPOSIT. Tenant shall pay a security deposit of $2,400, to be
returned within 21 days of move-out, less lawful deductions.

3. MAINTENANCE. Landlord is responsible for maintaining the premises in a
habitable condition. Tenant is responsible for minor repairs under $50.

4. ENTRY. Landlord shall provide at least 24 hours notice to enter the
premises except in emergencies.

5. TERMINATION. Tenant may terminate this lease early by paying a fee equal
to two months' rent.
"""

SAMPLE_NOTICE = """
NOTICE TO VACATE

This notice to vacate is served for non-payment of rent. Tenant has 3 days
to cure by paying the outstanding balance, or must vacate by the date listed
below: March 15.
"""

SAMPLE_SUBLEASE = """
SUBLEASE AGREEMENT

This sublease is entered into between Sublessor and Sublessee for the
remaining term of the original lease, which is incorporated by reference.
The sublessor has obtained written consent from the landlord to sublet.
"""


@pytest.fixture
def sample_lease_text() -> str:
    return SAMPLE_LEASE


@pytest.fixture
def sample_notice_text() -> str:
    return SAMPLE_NOTICE


@pytest.fixture
def sample_sublease_text() -> str:
    return SAMPLE_SUBLEASE

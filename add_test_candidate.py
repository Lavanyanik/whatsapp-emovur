"""Add test candidate to database for testing webhook functionality."""
import asyncio
import sys
sys.path.insert(0, '.')

from datetime import datetime, timezone
from app.database import AsyncSessionLocal
from app.models import Candidate

async def add_test_candidate():
    """Add a test candidate to the database."""
    async with AsyncSessionLocal() as db:
        # Check if candidate already exists
        from sqlalchemy import select
        result = await db.execute(select(Candidate).where(Candidate.phone == "919876543210"))
        existing = result.scalars().first()
        
        if existing:
            print(f"Candidate already exists: {existing}")
            return existing
        
        # Create new test candidate
        candidate = Candidate(
            candidate_name="Test User",
            phone="919876543210",
            role="Software Engineer",
            company="Test Company",
            status="pending",
            invite_sent_at=datetime.now(tz=timezone.utc)
        )
        
        db.add(candidate)
        await db.commit()
        await db.refresh(candidate)
        
        print(f"Added test candidate: {candidate}")
        return candidate

if __name__ == "__main__":
    asyncio.run(add_test_candidate())

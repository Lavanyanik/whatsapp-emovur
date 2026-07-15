"""Fast-forward script for testing the scheduler.

Sets invite_sent_at to 25 hours ago for a candidate matching the provided phone
number. Resets followup_sent_at and final_sent_at to NULL so the scheduler will
send the follow-up immediately.

Usage:
    python scripts\fast_forward.py --phone "+919999999999" [--preview]

Notes:
 - Ensure the FastAPI app (uvicorn) is running so the scheduler can pick up the change.
 - The script updates only the most recent candidate record matching the phone.
 - Only invite_sent_at, followup_sent_at, final_sent_at are modified.
 - Use --preview to run a dry-run which shows what would be changed without modifying the DB.
"""
import argparse
from datetime import datetime, timedelta
from pathlib import Path
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

# Import the Candidate model from the application
from app.models import Candidate


DB_FILE = Path(__file__).resolve().parents[1] / "whatsapp_emovur.db"
if not DB_FILE.exists():
    print(f"Database file not found at {DB_FILE}. Ensure you're running the script from the project root.")
    sys.exit(2)


def fast_forward(phone: str, preview: bool = False) -> int:
    """Update the candidate's timestamps. Returns 0 on success, non-zero on failure.

    If preview is True, do not commit any changes and just print what would be done.
    """
    engine = create_engine(f"sqlite:///{DB_FILE.as_posix()}", future=True, connect_args={"check_same_thread": False})

    with Session(engine) as session:
        stmt = select(Candidate).where(Candidate.phone == phone).order_by(Candidate.id.desc())
        result = session.execute(stmt)
        candidate = result.scalars().first()

        if candidate is None:
            print(f"No candidate found with phone={phone}")
            return 3

        now = datetime.utcnow()
        new_invite_time = now - timedelta(hours=25)

        # Show intended changes
        print(f"Candidate found: id={candidate.id} phone={candidate.phone} status={candidate.status}")
        print(f"Current invite_sent_at: {candidate.invite_sent_at}")
        print(f"Would set invite_sent_at => {new_invite_time.isoformat()} (UTC)")
        print("Would clear followup_sent_at and final_sent_at")

        if preview:
            print("Preview mode enabled: no changes written to the database.")
            return 0

        # Apply changes
        candidate.invite_sent_at = new_invite_time
        candidate.followup_sent_at = None
        candidate.final_sent_at = None

        session.add(candidate)
        session.commit()

        print(f"invite_sent_at set to {new_invite_time.isoformat()} (UTC). followup_sent_at and final_sent_at cleared.")
        return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Fast-forward invite_sent_at for a candidate to trigger reminders")
    parser.add_argument("--phone", required=True, help="Phone number of the candidate to update (exact match)")
    parser.add_argument("--preview", action="store_true", help="Show what would be changed without modifying the database")
    args = parser.parse_args()

    code = fast_forward(args.phone, preview=args.preview)
    sys.exit(code)


if __name__ == "__main__":
    main()

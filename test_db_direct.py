#!/usr/bin/env python
"""Direct database update test."""
import sqlite3

DB_PATH = "C:\\Users\\LAVANYA\\whatapp_emovur\\whatsapp_emovur.db"

def test_db_direct_update():
    """Test updating candidate directly in DB."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all columns
    cursor.execute("PRAGMA table_info(candidates)")
    cols = cursor.fetchall()
    print("Candidate table columns:")
    for col in cols:
        print(f"  {col[1]}: {col[2]}")
    
    # Get candidate 23
    cursor.execute("SELECT * FROM candidates WHERE id = 23")
    row = cursor.fetchone()
    if row:
        col_names = [desc[0] for desc in cursor.description]
        print(f"\nCandidate 23 before:")
        for name, val in zip(col_names, row):
            print(f"  {name}: {val}")
    
    # Try to update
    print(f"\nUpdating candidate 23...")
    cursor.execute("""
        UPDATE candidates 
        SET status = 'interested', candidate_response = 'Interested', response_received_at = datetime('now')
        WHERE id = 23
    """)
    conn.commit()
    
    # Verify
    cursor.execute("SELECT * FROM candidates WHERE id = 23")
    row = cursor.fetchone()
    if row:
        col_names = [desc[0] for desc in cursor.description]
        print(f"\nCandidate 23 after:")
        for name, val in zip(col_names, row):
            print(f"  {name}: {val}")
    
    conn.close()

if __name__ == "__main__":
    test_db_direct_update()

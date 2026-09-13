#!/usr/bin/env python3
"""
MetrCheck AI – History Test Record Cleanup Script.
Safely and idempotently removes synthetic test records (e.g., test-alpino-*, test-*)
from the development/production database without affecting genuine user analyses.
"""

import os
import sys
import sqlite3
import argparse

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, 'metrc_check.db')
UPLOAD_DIR = os.path.join(BACKEND_DIR, 'uploads')

PROTECTED_ASSETS = {
    'alpino_front.png', 'alpino_back.png',
    'Alpino-Front.png', 'Alpino-Back.png',
    'front.png', 'back.png',
    'TakaTak-Front.jpeg', 'TakaTak-Back.jpeg',
    'Lays-Front.jpeg', 'Lays-Back.jpeg'
}


def clean_test_records(dry_run: bool = False):
    mode_str = 'DRY RUN (no changes)' if dry_run else 'LIVE EXECUTION'
    print(f"[*] MetrCheck AI History Cleanup Script")
    print(f"[*] Database path: {DB_PATH}")
    print(f"[*] Uploads dir:   {UPLOAD_DIR}")
    print(f"[*] Mode:          {mode_str}")

    if not os.path.exists(DB_PATH):
        print(f"[!] Error: Database not found at {DB_PATH}")
        return False

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get total before
    cur.execute('SELECT count(*) FROM analyses')
    total_before = cur.fetchone()[0]

    # Find test records_suite
    query = """SELECT id, product_name, image_filename, score, status, created_at 
               FROM analyses 
               WHERE id LIKE 'test-%' OR id LIKE 'test_%' OR id LIKE 'demo-%' OR id IN ('1', '2', '3')
               ORDER BY created_at DESC"""
    cur.execute(query)
    test_rows = cur.fetchall()

    print(f"\n[*] Total records in database: {total_before}")
    print(f"[*] Test/fixture records found: {len(test_rows)}")

    for r in test_rows:
        print(f"    - ID: {r[0]} | Product: {r[1]} | Created: {r[5]} | Score: {r[3]} | Status: {r[4]}")

    if not test_rows:
        print("\n[+] Database is already clean. No synthetic test records found.")
        conn.close()
        return True

    if dry_run:
        print(f"\n[*] DRY RUN: Would delete {len(test_rows)} test record(s). Database untouched.")
        conn.close()
        return True

    # Delete test records from DB
    del_ql = """DELETE FROM analyses 
                WHERE id LIKE 'test-%' OR id LIKE 'test_%' OR id LIKE 'demo-%' OR id IN ('1', '2', '3')"""
    cur.execute(del_ql)
    deleted_count = cur.rowcount
    conn.commit()

    # Safely clean associated uploaded files if they are specific to test IDs
    cleaned_files = 0
    if os.path.exists(UPLOAD_DIR):
        for r in test_rows:
            test_id = r[0]
            try:
                for item in os.listdir(UPLOAD_DIR):
                    if item.startswith(f"{test_id}_") and item not in PROTECTED_ASSETS:
                        filepath = os.path.join(UPLOAD_DIR, item)
                        if os.path.isfile(filepath):
                            os.remove(filepath)
                            cleaned_files += 1
                            print(f"    - Removed test upload file: {item}")
            except Exception as e:
                print(f"[!] Error cleaning files for {test_id}: {e}")

    # Get total after
    cur.execute('SELECT count(*) FROM analyses')
    total_after = cur.fetchone()[0]
    conn.close()

    print(f"\n[+] Successfully cleaned database!")
    print(f"    - Deleted test records: {deleted_count}")
    print(f"    - Cleaned test files:   {cleaned_files}")
    print(f"    - Remaining genuine records: {total_after}")
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Cleanup test records from MetrCheck AI database')
    parser.add_argument('--dry-run', action='store_true', help='Preview records to be deleted without modifying DB')
    args = parser.parse_args()
    clean_test_records(dry_run=args.dry_run)

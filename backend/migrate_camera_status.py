"""
Database migration script to add processing_status and completion_message to cameras table
Run this script to update your existing database schema
"""

import sqlite3
import os

# Get the database path
db_path = os.path.join(os.path.dirname(__file__), 'nozzle_detection.db')

print(f"Migrating database: {db_path}")

try:
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(cameras)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Add processing_status column if it doesn't exist
    if 'processing_status' not in columns:
        print("Adding processing_status column...")
        cursor.execute("""
            ALTER TABLE cameras 
            ADD COLUMN processing_status TEXT DEFAULT 'idle'
        """)
        print("✓ Added processing_status column")
    else:
        print("✓ processing_status column already exists")
    
    # Add completion_message column if it doesn't exist
    if 'completion_message' not in columns:
        print("Adding completion_message column...")
        cursor.execute("""
            ALTER TABLE cameras 
            ADD COLUMN completion_message TEXT
        """)
        print("✓ Added completion_message column")
    else:
        print("✓ completion_message column already exists")
    
    # Commit changes
    conn.commit()
    print("\n✓ Database migration completed successfully!")
    
except sqlite3.Error as e:
    print(f"\n✗ Error during migration: {e}")
    
finally:
    if conn:
        conn.close()

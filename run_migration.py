"""
Quick migration to add universal_paper_trading_config column to device_settings
"""
import sqlite3
import sys

def add_column():
    db_path = "data/sqlite/jasper_trades.db"
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column already exists
        cursor.execute("PRAGMA table_info(device_settings)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if "universal_paper_trading_config" in columns:
            print("✓ Column 'universal_paper_trading_config' already exists")
            return True
        
        # Add the column
        print("Adding column 'universal_paper_trading_config'...")
        cursor.execute("ALTER TABLE device_settings ADD COLUMN universal_paper_trading_config TEXT")
        conn.commit()
        
        print("✓ Column added successfully")
        return True
        
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("✓ Column already exists")
            return True
        print(f"✗ Database error: {e}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    success = add_column()
    sys.exit(0 if success else 1)
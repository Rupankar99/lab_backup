import json
from pathlib import Path
import sys
import uuid
import threading
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))
    
from incident_db.db.connection import get_connection
from incident_db.models.queue import QueueModel

class SQLiteQueue:
    """Thread-safe queue implementation using SQLite3."""

    def __init__(self):
        self.lock = threading.Lock()
        conn = get_connection()
        self.queue_model = QueueModel(conn)
    
    def enqueue(self, data: Any) -> str:
        """Add an item to the queue."""
        item_id = str(uuid.uuid4())
        data_json = json.dumps(data)

        self.queue_model.raw_execute("INSERT INTO queue (id, data) VALUES (?, ?)", (item_id, data_json))
        
        return item_id
    
    # def complete(self, item_id: str):
    #     """Mark an item as completed."""
    #     conn = get_connection(self.db_path)
    #     cursor = conn.cursor()
    #     cursor.execute("""
    #         UPDATE queue 
    #         SET status = 'completed', processed_at = CURRENT_TIMESTAMP 
    #         WHERE id = ?
    #     """, (item_id,))
    #     conn.commit()
    #     conn.close()
    
    # def fail(self, item_id: str):
    #     """Requeue a failed item."""
    #     conn = get_connection(self.db_path)
    #     cursor = conn.cursor()
    #     cursor.execute("""
    #         UPDATE queue 
    #         SET status = 'pending', consumer_id = NULL 
    #         WHERE id = ?
    #     """, (item_id,))
    #     conn.commit()
    #     conn.close()
    
    def get_stats(self) -> dict:
        """Get queue status counts."""
        data = self.queue_model.raw_execute("SELECT status, COUNT(*) as count FROM queue GROUP BY status")
        items = data.fetchall()
        stats = {row['status']: row['count'] for row in items}

        return stats

"""
LangGraph Notification Agent with Database Persistence
Handles multiple notification types: Jira, Slack, Email, SMS
Uses ReAct pattern with database storage
"""

import json
from typing import TypedDict, Annotated, Sequence, Literal, List
from datetime import datetime
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langchain_anthropic import ChatAnthropic

from langchain_openai import ChatOpenAI
import httpx

client = httpx.Client(verify=False)

import operator
import sqlite3
from enum import Enum

# ============================================================================
# Database Schema and Models
# ============================================================================

class NotificationType(str, Enum):
    JIRA = "jira"
    SLACK = "slack"
    EMAIL = "email"
    SMS = "sms"

class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    RETRY = "retry"

class DatabaseManager:
    """Manages database operations for notifications"""
    
    def __init__(self, db_path: str = "notifications.db"):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_type TEXT NOT NULL,
                recipient TEXT NOT NULL,
                subject TEXT,
                message TEXT NOT NULL,
                metadata TEXT,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sent_at TIMESTAMP,
                error_message TEXT,
                retry_count INTEGER DEFAULT 0
            )
        """)
        
        # Notification history/audit log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_id INTEGER,
                status TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT,
                FOREIGN KEY (notification_id) REFERENCES notifications(id)
            )
        """)
        
        # Notification templates
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_type TEXT NOT NULL,
                template_name TEXT NOT NULL,
                template_content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(notification_type, template_name)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def save_notification(self, notification_type: str, recipient: str, 
                         subject: str, message: str, metadata: dict = None,
                         status: str = NotificationStatus.PENDING) -> int:
        """Save a notification to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO notifications 
            (notification_type, recipient, subject, message, metadata, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (notification_type, recipient, subject, message, 
              json.dumps(metadata or {}), status))
        
        notification_id = cursor.lastrowid
        
        # Add to history
        cursor.execute("""
            INSERT INTO notification_history (notification_id, status, details)
            VALUES (?, ?, ?)
        """, (notification_id, status, "Notification created"))
        
        conn.commit()
        conn.close()
        
        return notification_id
    
    def update_notification_status(self, notification_id: int, status: str, 
                                   error_message: str = None):
        """Update notification status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        sent_at = datetime.now().isoformat() if status == NotificationStatus.SENT else None
        
        cursor.execute("""
            UPDATE notifications 
            SET status = ?, sent_at = ?, error_message = ?
            WHERE id = ?
        """, (status, sent_at, error_message, notification_id))
        
        # Add to history
        cursor.execute("""
            INSERT INTO notification_history (notification_id, status, details)
            VALUES (?, ?, ?)
        """, (notification_id, status, error_message or "Status updated"))
        
        conn.commit()
        conn.close()
    
    def get_notification(self, notification_id: int) -> dict:
        """Get notification by ID"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, notification_type, recipient, subject, message, 
                   metadata, status, created_at, sent_at, error_message
            FROM notifications WHERE id = ?
        """, (notification_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row[0],
                "notification_type": row[1],
                "recipient": row[2],
                "subject": row[3],
                "message": row[4],
                "metadata": json.loads(row[5]),
                "status": row[6],
                "created_at": row[7],
                "sent_at": row[8],
                "error_message": row[9]
            }
        return None
    
    def get_notifications_by_status(self, status: str) -> List[dict]:
        """Get all notifications with a specific status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, notification_type, recipient, subject, message, 
                   metadata, status, created_at
            FROM notifications WHERE status = ?
            ORDER BY created_at DESC
        """, (status,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": row[0],
                "notification_type": row[1],
                "recipient": row[2],
                "subject": row[3],
                "message": row[4],
                "metadata": json.loads(row[5]),
                "status": row[6],
                "created_at": row[7]
            }
            for row in rows
        ]

# ============================================================================
# State Definition
# ============================================================================

class AgentState(TypedDict):
    """State for the notification agent"""
    user_query: Annotated[Sequence[BaseMessage], operator.add]
    answer: str
    notifications_created: List[int]
    current_step: str

# ============================================================================
# Notification Tools (with Database Integration)
# ============================================================================

# Initialize database manager
db = DatabaseManager()

@tool
def send_jira_notification(project: str, issue_type: str, summary: str, 
                          description: str, assignee: str = None) -> str:
    """
    Create a Jira notification/ticket and save to database.
    
    Args:
        project: Jira project key (e.g., 'MYAPP')
        issue_type: Type of issue (e.g., 'Bug', 'Task', 'Story')
        summary: Brief summary of the issue
        description: Detailed description
        assignee: Optional assignee username
    
    Returns:
        Status message with notification ID
    """
    metadata = {
        "project": project,
        "issue_type": issue_type,
        "assignee": assignee
    }
    
    # Save to database
    notification_id = db.save_notification(
        notification_type=NotificationType.JIRA,
        recipient=project,
        subject=summary,
        message=description,
        metadata=metadata,
        status=NotificationStatus.PENDING
    )
    
    # Simulate sending (replace with actual Jira API call)
    try:
        # Mock Jira API call
        issue_key = f"{project}-{notification_id}"
        print(f"[JIRA] Creating issue: {issue_key}")
        
        # Update status to sent
        db.update_notification_status(notification_id, NotificationStatus.SENT)
        
        return f"✓ Jira ticket created: {issue_key} (DB ID: {notification_id})"
    except Exception as e:
        db.update_notification_status(notification_id, NotificationStatus.FAILED, str(e))
        return f"✗ Failed to create Jira ticket: {str(e)}"

@tool
def send_slack_notification(channel: str, message: str, 
                           mention_users: List[str] = None) -> str:
    """
    Send a Slack notification and save to database.
    
    Args:
        channel: Slack channel name (e.g., '#dev-team', '@username')
        message: Message content
        mention_users: List of users to mention (e.g., ['@john', '@jane'])
    
    Returns:
        Status message with notification ID
    """
    metadata = {
        "channel": channel,
        "mentions": mention_users or []
    }
    
    # Save to database
    notification_id = db.save_notification(
        notification_type=NotificationType.SLACK,
        recipient=channel,
        subject="Slack Message",
        message=message,
        metadata=metadata,
        status=NotificationStatus.PENDING
    )
    
    # Simulate sending (replace with actual Slack API call)
    try:
        print(f"[SLACK] Sending to {channel}: {message[:50]}...")
        
        # Update status to sent
        db.update_notification_status(notification_id, NotificationStatus.SENT)
        
        return f"✓ Slack message sent to {channel} (DB ID: {notification_id})"
    except Exception as e:
        db.update_notification_status(notification_id, NotificationStatus.FAILED, str(e))
        return f"✗ Failed to send Slack message: {str(e)}"

@tool
def send_email_notification(to: str, subject: str, body: str, 
                           cc: List[str] = None, attachments: List[str] = None) -> str:
    """
    Send an email notification and save to database.
    
    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body content
        cc: Optional list of CC recipients
        attachments: Optional list of attachment file paths
    
    Returns:
        Status message with notification ID
    """
    metadata = {
        "to": to,
        "cc": cc or [],
        "attachments": attachments or []
    }
    
    # Save to database
    notification_id = db.save_notification(
        notification_type=NotificationType.EMAIL,
        recipient=to,
        subject=subject,
        message=body,
        metadata=metadata,
        status=NotificationStatus.PENDING
    )
    
    # Simulate sending (replace with actual email service)
    try:
        print(f"[EMAIL] Sending to {to}: {subject}")
        
        # Update status to sent
        db.update_notification_status(notification_id, NotificationStatus.SENT)
        
        return f"✓ Email sent to {to} (DB ID: {notification_id})"
    except Exception as e:
        db.update_notification_status(notification_id, NotificationStatus.FAILED, str(e))
        return f"✗ Failed to send email: {str(e)}"

@tool
def send_sms_notification(phone_number: str, message: str) -> str:
    """
    Send an SMS notification and save to database.
    
    Args:
        phone_number: Recipient phone number (E.164 format recommended)
        message: SMS message content (max 160 chars for single SMS)
    
    Returns:
        Status message with notification ID
    """
    metadata = {
        "phone_number": phone_number,
        "message_length": len(message)
    }
    
    # Save to database
    notification_id = db.save_notification(
        notification_type=NotificationType.SMS,
        recipient=phone_number,
        subject="SMS",
        message=message,
        metadata=metadata,
        status=NotificationStatus.PENDING
    )
    
    # Simulate sending (replace with actual SMS service like Twilio)
    try:
        print(f"[SMS] Sending to {phone_number}: {message[:50]}...")
        
        # Update status to sent
        db.update_notification_status(notification_id, NotificationStatus.SENT)
        
        return f"✓ SMS sent to {phone_number} (DB ID: {notification_id})"
    except Exception as e:
        db.update_notification_status(notification_id, NotificationStatus.FAILED, str(e))
        return f"✗ Failed to send SMS: {str(e)}"

@tool
def get_notification_status(notification_id: int) -> str:
    """
    Get the status of a notification by its database ID.
    
    Args:
        notification_id: Database ID of the notification
    
    Returns:
        Notification status details
    """
    notification = db.get_notification(notification_id)
    
    if notification:
        return json.dumps(notification, indent=2)
    else:
        return f"Notification ID {notification_id} not found"

@tool
def list_pending_notifications() -> str:
    """
    List all pending notifications that haven't been sent yet.
    
    Returns:
        List of pending notifications
    """
    pending = db.get_notifications_by_status(NotificationStatus.PENDING)
    
    if pending:
        return json.dumps(pending, indent=2)
    else:
        return "No pending notifications"

# ============================================================================
# Notification Agent (ReAct Pattern)
# ============================================================================

def notification_agent(state: AgentState) -> AgentState:
    """
    Main notification agent using ReAct pattern
    Similar to your search_agent but for notifications
    """
    print("--- Notification Agent (ReAct) ---")
    
    # Initialize LLM
    llm = ChatOpenAI(
    base_url="https://genailab.tcs.in",
    model="azure_ai/genailab-maas-DeepSeek-V3-0324",
    api_key="sk-",
    http_client=client
    )
    
    # Create ReAct agent with all notification tools
    tools = [
        send_jira_notification,
        send_slack_notification,
        send_email_notification,
        send_sms_notification,
        get_notification_status,
        list_pending_notifications
    ]
    
    agent = create_react_agent(llm, tools)
    
    # Invoke agent with user query
    result = agent.invoke({"messages": state["user_query"]})
    
    # Extract final message content
    state['answer'] = result["messages"][-1].content
    state['current_step'] = "completed"
    
    # Extract notification IDs from the conversation
    # (You can enhance this to track IDs more reliably)
    notification_ids = []
    for msg in result["messages"]:
        if hasattr(msg, 'content') and 'DB ID:' in msg.content:
            # Simple extraction - enhance as needed
            try:
                id_part = msg.content.split('DB ID:')[1].split(')')[0].strip()
                notification_ids.append(int(id_part))
            except:
                pass
    
    state['notifications_created'] = notification_ids
    
    return state

# ============================================================================
# Graph Construction
# ============================================================================

def create_notification_workflow():
    """Create the LangGraph workflow for notifications"""
    
    workflow = StateGraph(AgentState)
    
    # Add the notification agent node
    workflow.add_node("notification_agent", notification_agent)
    
    # Set entry point
    workflow.set_entry_point("notification_agent")
    
    # Add edge to end
    workflow.add_edge("notification_agent", END)
    
    return workflow.compile()

# ============================================================================
# Usage Examples
# ============================================================================

async def main():
    """Example usage of the notification agent"""
    
    # Create the workflow
    graph = create_notification_workflow()
    
    # Example 1: Create Jira ticket and notify Slack
    print("\n" + "="*80)
    print("EXAMPLE 1: Jira + Slack Notification")
    print("="*80 + "\n")
    
    state1 = {
        "user_query": [HumanMessage(content="""
            Create a Jira ticket in project MYAPP for a bug: 'Login button not working on mobile'.
            Description: 'Users report the login button is unresponsive on iOS devices.'
            Then send a Slack message to #dev-team channel about this new bug.
        """)],
        "answer": "",
        "notifications_created": [],
        "current_step": "started"
    }
    
    result1 = await graph.ainvoke(state1)
    print(f"\nAnswer: {result1['answer']}")
    print(f"Notifications Created: {result1['notifications_created']}")
    
    # Example 2: Multi-channel notification
    print("\n" + "="*80)
    print("EXAMPLE 2: Multi-Channel Notification")
    print("="*80 + "\n")
    
    state2 = {
        "user_query": [HumanMessage(content="""
            We have a production incident! Send notifications:
            1. Create a Jira incident ticket in project OPS
            2. Send Slack alert to #incidents channel
            3. Send email to ops-team@company.com
            4. Send SMS to on-call engineer at +1234567890
            
            Message: "Production API is down - investigating"
        """)],
        "answer": "",
        "notifications_created": [],
        "current_step": "started"
    }
    
    result2 = await graph.ainvoke(state2)
    print(f"\nAnswer: {result2['answer']}")
    print(f"Notifications Created: {result2['notifications_created']}")
    
    # Example 3: Check notification status
    print("\n" + "="*80)
    print("EXAMPLE 3: Check Notification Status")
    print("="*80 + "\n")
    
    state3 = {
        "user_query": [HumanMessage(content="""
            Get the status of notification ID 1 and list all pending notifications.
        """)],
        "answer": "",
        "notifications_created": [],
        "current_step": "started"
    }
    
    result3 = await graph.ainvoke(state3)
    print(f"\nAnswer: {result3['answer']}")

# ============================================================================
# Direct Database Query Examples
# ============================================================================

def query_database_examples():
    """Show direct database query examples"""
    
    print("\n" + "="*80)
    print("DATABASE QUERY EXAMPLES")
    print("="*80 + "\n")
    
    # Get pending notifications
    pending = db.get_notifications_by_status(NotificationStatus.PENDING)
    print(f"Pending notifications: {len(pending)}")
    
    # Get sent notifications
    sent = db.get_notifications_by_status(NotificationStatus.SENT)
    print(f"Sent notifications: {len(sent)}")
    
    # Get specific notification
    if sent:
        notification = db.get_notification(sent[0]['id'])
        print(f"\nSample notification:\n{json.dumps(notification, indent=2)}")

if __name__ == "__main__":
    import asyncio
    
    # Run the agent examples
    asyncio.run(main())
    
    # Show database queries
    query_database_examples()

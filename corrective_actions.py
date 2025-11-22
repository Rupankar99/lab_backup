import httpx
import warnings
from datetime import datetime
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
import sqlite3

warnings.filterwarnings("ignore", category=UserWarning)

# ===== Configuration =====
API_KEY = ".."
API_ENDPOINT = ".."
LLM_MODEL = "azure/genailab-maas-gpt-4o"
EMBEDDING_MODEL = "azure/genailab-maas-text-embedding-3-large"
PERSIST_DIR = r"C:\Users\GENAIKOLGPUSR15\Desktop\Incident_management\incident_db\data\chroma_index"
# SQLite Database Configuration
DB_PATH = r"C:\Users\GENAIKOLGPUSR15\Desktop\Incident_management\incident_db\data\incident_iq.db"

# ===== Initialize Clients =====
client = httpx.Client(verify=False)

embedding_model = OpenAIEmbeddings(
    base_url=API_ENDPOINT,
    api_key=API_KEY,
    model=EMBEDDING_MODEL,
    http_client=client,
    check_embedding_ctx_length=False
)

llm = ChatOpenAI(
    base_url=API_ENDPOINT,
    api_key=API_KEY,
    model=LLM_MODEL,
    temperature=0.3,
    http_client=client
)

vectordb = Chroma(
    persist_directory=PERSIST_DIR,
    embedding_function=embedding_model
)


# ===== Core Functions =====
def process_corrective_action(data):
    """
    Main function to process corrective action request
    Extracts data, queries RAG, and updates database
    """
    try:        
        # Extract required fields from message data

        classifier_id = data.get('payload_id')
        incident_description = data.get('error_message', '')

        if not classifier_id:
            raise ValueError("Missing classifier_id in data")
        
        incident_description = "No incident description provided"
        
        print(f"🔍 Querying RAG for incident: {incident_description[:100]}...")
        
        # Get corrective action from RAG
        corrective_action = get_corrective_action_from_rag(incident_description)
        
        print(f"💡 Generated corrective action: {corrective_action[:100]}...")
        
        # Update database
        update_corrective_action_db(classifier_id, corrective_action)
        
        print(f"✅ Successfully processed corrective action for ID: {classifier_id}")
        return True
        
    except Exception as e:
        print(f"❌ Error processing corrective action: {e}")
        return False


def get_corrective_action_from_rag(query):
    """
    Retrieve similar incidents and generate corrective action using RAG
    """
    try:
        # Search vector database for similar incidents
        results = vectordb.similarity_search(query, k=3)
        
        if not results:
            context = "No similar historical cases found."
        else:
            # Build context from retrieved documents
            context = "\n\n".join([
                f"Case {i+1}: {doc.page_content}" 
                for i, doc in enumerate(results)
            ])
        
        # Create prompt for LLM
        prompt = f"""Based on the following incident and similar historical cases, provide a clear and actionable corrective action.

**Current Incident:**
{query}

**Similar Historical Cases:**
{context}

**Instructions:**
- Provide specific, actionable steps
- Be concise and clear
- Focus on resolution and prevention
- If no similar cases exist, provide general best practices

**Corrective Action:**"""
        
        # Generate corrective action using LLM
        response = llm.invoke(prompt)
        corrective_action = response.content.strip()
        
        return corrective_action
        
    except Exception as e:
        print(f" Error in RAG query: {e}")
        raise


def update_corrective_action_db(classifier_id, corrective_action):
    """
    Update classifier_output table with corrective action and timestamps
    """
    conn = None
    cursor = None
    
    try:
        # Connect to SQLite database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Update query
        query = """
            UPDATE classifier_outputs 
            SET corrective_action = ?,
                processed_at = ?,
                updated_at = ?
            WHERE payload_id = ?
        """
        
        # Execute update
        cursor.execute(query, (corrective_action, now, now, classifier_id))
        
        # Check if row was updated
        if cursor.rowcount == 0:
            raise ValueError(f"No record found with classifier_id: {classifier_id}")
        
        conn.commit()
        print(f"💾 Database updated successfully for ID: {classifier_id}")
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Database error: {e}")
        raise
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ===== Message Handler (Integration Point) =====
def handle_message(message):
    """
    Main message handler - integrates with your existing system
    """
    if message.get('task') == 'set_corrective_action':
        process_corrective_action(message['data'])

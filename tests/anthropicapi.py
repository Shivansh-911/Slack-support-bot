import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

from config import settings
import django

django.setup()

from agent.services.anthropic_client_service import AnthropicClientService

client = AnthropicClientService().build()
page = client.beta.sessions.retrieve(session_id="sesn_01B9263wFicbpB1gEXdsZ2X3")
print("agent_id:", page.agent.id)
print("list_cost:", page.usage.list_cost.amount)
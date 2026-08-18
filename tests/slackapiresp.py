
from sys import float_repr_style
from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackAPI:

    def fetch(self):

        query = "all the interns who belong to this channel in:<#C0BJV4LF6N7>"
        action_token = None
        channel_types = ['public_channel','private_channel']
        content_types = ["messages"]
        include_bots = False
        include_deleted_users = None
        before = None
        after = None
        include_context_messages = False
        context_channel_id = None
        cursor = None
        limit = None
        sort = None
        sort_dir = None
        include_message_blocks = True
        highlight = None
        term_clauses = None
        modifiers = []
        include_archived_channels = None
        disable_semantic_search = False

        client = WebClient(token=settings.SLACK_USER_TOKEN)
        params = {
            "query": query,
            "action_token": action_token,
            "channel_types": channel_types,
            "content_types": content_types,
            "include_bots": include_bots,
            "include_deleted_users": include_deleted_users,
            "before": before,
            "after": after,
            "include_context_messages": include_context_messages,
            "context_channel_id": context_channel_id,
            "cursor": cursor,
            "limit": limit,
            "sort": sort,
            "sort_dir": sort_dir,
            "include_message_blocks": include_message_blocks,
            "highlight": highlight,
            "term_clauses": term_clauses,
            "modifiers": modifiers,
            "include_archived_channels": include_archived_channels,
            "disable_semantic_search": disable_semantic_search,
        }
        params = {key: value for key, value in params.items() if value is not None}

        try:
            response = client.api_call("assistant.search.context", json=params)
        except Exception as error:
            return {"error": f"Slack search failed: {error}"}

        results = response.get("results", {})
        messages = results["messages"]
        print("RESULTS : ")
        print(results)

        print("MESSAGES : ")
        print(messages)

        return 



    def joinchannel(self):
        client = WebClient(token=settings.SLACK_BOT_TOKEN)   

        try:
            response = client.conversations_join(
                    channel= 'C0BJN116WQ5'
            )
        except Exception as error:
            return {"error": f"Slack search failed: {error}"}
        
        print(response)
        
        return 

    def sendinvite(self):
        client = WebClient(token=settings.SLACK_BOT_TOKEN)   

        try:
            response = client.conversations_invite(
                channel= 'C0BJV4LF6N7',
                users= 'U0AQXU5JRE1'
            )
        except Exception as error:
            return {"error": f"Slack search failed: {error}"}
        
        print(response)
        
        return 

    def userinfo(self):
        client = WebClient(token=settings.SLACK_BOT_TOKEN)   

        try:
            response = client.users_info(
                user= 'U0AQXU5JRE1'
            )
        except Exception as error:
            return {"error": f"Slack search failed: {error}"}
        
        print(response)
        
        return 


    def listchannels(self):
        client = WebClient(token=settings.SLACK_BOT_TOKEN)

        try:
            response = client.users_conversations(
                    types= 'public_channel,private_channel'
            )
        except Exception as error:
            return {"error": f"Slack search failed: {error}"}
        
        print(response)
        
        return 

    def listusergroup(self):
        client = WebClient(token=settings.SLACK_BOT_TOKEN)

        try:
            response = client.usergroups_list(
            )
        except Exception as error:
            return {"error": f"Slack search failed: {error}"}
        
        print(response)
        
        return 

    def main(self):
        return self.listusergroup()


if __name__ == "__main__":
    import os
    import sys
    import django

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    print(SlackAPI().main())
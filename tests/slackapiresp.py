
from sys import float_repr_style
from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

class SlackAPI:

    def fetch(self):
        # Local import: this script is run directly (`python tests/slackapiresp.py`),
        # and sys.path only gets the project root added in the __main__ guard
        # below, which runs after top-level imports are already resolved — a
        # module-level import of an `agent.*` package would fail before that
        # guard ever executes.
        from agent.services.slack.slack_search_result_formatter import SlackSearchResultFormatter

        channel_list = "in:<#C03E3P80CDV> OR in:<#C03EBMTEC14> OR in:<#C03F83XPEJU> OR in:<#C04AFL2GECE> OR in:<#C04AZRNAW7L> OR in:<#C05J50UV99R> OR in:<#C07RF9Y304S> OR in:<#C0APS04G7DM> OR in:<#C0B3LET9YQ4> OR in:<#C0BJN116WQ5>  OR in:<#C0BM44A3YCW>"
        user_query = "crictoday on development"
        # query = "developement on crictoday in:<#C04AZRNAW7L>"
        query = f'{user_query} {channel_list}'
        action_token = None
        channel_types = ['public_channel','private_channel']
        content_types = ["messages"]
        include_bots = True
        include_deleted_users = True
        before = None
        after = None
        include_context_messages = True
        context_channel_id = None
        cursor = None
        limit = 3
        sort = "score"
        sort_dir = "desc"
        include_message_blocks = True
        highlight = False
        term_clauses = None
        modifiers = []
        include_archived_channels = None
        disable_semantic_search = False

        client = WebClient(token=settings.SLACK_USER_TOKEN)
        params = {
            "query": query,
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
        print("Query")
        print(query)
        print("RAW RESULTS : ")
        print(response)

        formatted = SlackSearchResultFormatter().format(response.data)
        print("\nFORMATTED RESULTS : ")
        print(formatted)

        # print("MESSAGES : ")
        # print(messages)

        return formatted



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
                user= 'U0B7C6RBUD8'
            )
        except Exception as error:
            return {"error": f"Slack search failed: {error}"}
        
        print(response)
        
        return 


    def listchannels(self):
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        mapping = {}
        cursor = None
        try:
            while True:
                response = client.users_conversations(
                    types='public_channel,private_channel',
                    limit=200,
                    cursor=cursor,
                )
                for channel in response.get('channels', []):
                    name = channel.get('name')
                    channel_id = channel.get('id')
                    if name and channel_id:
                        if channel_id == 'C0BJV4LF6N7':
                            continue
                        mapping[channel_id] = name
                cursor = response.get('response_metadata', {}).get('next_cursor')
                if not cursor:
                    break
        except SlackApiError:
            pass
        return mapping

    def listusergroup(self):
        client = WebClient(token=settings.SLACK_BOT_TOKEN)

        try:
            response = client.usergroups_list(
            )
        except Exception as error:
            return {"error": f"Slack search failed: {error}"}
        
        print(response)
        
        return 

    def get_channel_name(self, channel_id):
        client = WebClient(token=settings.SLACK_BOT_TOKEN)
        try:
            response = client.conversations_info(channel=channel_id)
            channel = response.get('channel')
            return channel.get('name')
        except SlackApiError:
            pass

    def list_channel_members(self):
        client = WebClient(token=settings.SLACK_USER_TOKEN)
        try:
            response = client.conversations_history(channel="C04GJCY2ENA",limit=1)
            return response
        except SlackApiError:
            pass

    def list_conversation(self):
        client = WebClient(token=settings.SLACK_USER_TOKEN)
        try:
            response = client.conversations_history(channel="C07RF9Y304S",limit=5)
            return response
        except SlackApiError:
            pass

    def list_with_members(self):
        client = WebClient(token=settings.SLACK_USER_TOKEN)
        try:
            response = client.usergroups_list(include_count=True, include_disabled=False)
        except SlackApiError as error:
            return {'error': f'Slack request failed: {error}'}
        groups = []
        for usergroup in response.get('usergroups', []):
            groups.append({
                'id': usergroup.get('id'),
                'name': usergroup.get('name') or '',
                'handle': usergroup.get('handle') or '',
                'description': usergroup.get('description') or '',
                'user_count': usergroup.get('user_count'),
                'users': self._members(client, usergroup.get('id')),
            })
        return groups

    def _members(self, client, usergroup_id):
        try:
            response = client.usergroups_users_list(usergroup=usergroup_id)
        except SlackApiError:
            return []
        return response.get('users', [])


    def main(self):
        return self.fetch()


if __name__ == "__main__":
    import os
    import sys
    import django

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    django.setup()

    print(SlackAPI().main())
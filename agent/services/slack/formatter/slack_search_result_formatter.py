"""Formats an `assistant.search.context` response into a compact,
flattened text block instead of raw JSON.

Response shape this assumes (per
https://docs.slack.dev/reference/methods/assistant.search.context):

    {
      "ok": true,
      "results": {
        "messages": [{
          "author_name": str, "author_user_id": str, "author_email": str,
          "team_id": str, "channel_id": str, "channel_name": str,
          "message_ts": str, "content": str, "is_author_bot": bool,
          "permalink": str, "reply_count": int (optional),
          "context_messages": {                      # optional
            "before": [{"text": str, "user_id": str, "ts": str, "author_name": str}],
            "after": [...]
          }
        }],
        "files": [...], "channels": [...]             # always empty here —
                                                        # SlackChannelSearchAssistantService
                                                        # forces content_types to ["messages"]
      },
      "response_metadata": {"next_cursor": str}
    }

`team_id`, `author_email`, and any `blocks` payload are dropped — none of
them help the agent answer, and dropping them is most of the token
saving. `content_types` being messages-only means `files`/`channels`
are ignored rather than formatted.
"""

from agent.services.slack.formatter.slack_text_block_formatter import join_blocks


class SlackSearchResultFormatter:
    EMPTY_MESSAGE = "No results found."

    def format(self, response_data):
        response_data = response_data or {}
        messages = (response_data.get("results") or {}).get("messages") or []
        blocks = [self._format_message(message) for message in messages]
        text = join_blocks(blocks, self.EMPTY_MESSAGE)

        cursor = (response_data.get("response_metadata") or {}).get("next_cursor")
        if cursor:
            text += (
                f"\n\n{len(messages)} result(s) shown. More available — "
                f'pass cursor="{cursor}" to continue.'
            )
        return text

    def _format_message(self, message):
        lines = [
            self._header(message),
            message.get("permalink", ""),
        ]

        context = message.get("context_messages") or {}
        for context_message in context.get("before") or []:
            lines.append(self._context_line("↑", context_message))

        lines.append(message.get("content", ""))

        for context_message in context.get("after") or []:
            lines.append(self._context_line("↓", context_message))

        return "\n".join(line for line in lines if line)

    def _header(self, message):
        header = (
            f"#{message.get('channel_name', '?')} ({message.get('channel_id', '?')}) — "
            f"{message.get('author_name', '?')} ({message.get('author_user_id', '?')}) "
            f"@ {message.get('message_ts', '?')}"
        )
        reply_count = message.get("reply_count")
        if reply_count:
            header += f" · {reply_count} repl{'y' if reply_count == 1 else 'ies'}"
        if message.get("is_author_bot"):
            header += " · bot"
        return header

    def _context_line(self, marker, context_message):
        text = context_message.get("text", "")
        if not text:
            return ""
        author = context_message.get("author_name") or context_message.get("user_id", "?")
        return f"  {marker} {author}: {text}"


__all__ = ["SlackSearchResultFormatter"]

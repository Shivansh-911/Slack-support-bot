"""Formats a SlackConversationRepliesService response into a compact,
flattened text block instead of raw JSON.

Same record shape and layout as SlackConversationHistoryFormatter — kept
as its own file rather than shared, matching slack_text_block_formatter's
own convention that each tool owns its formatter even when the record
shape overlaps with another tool's.
"""

from agent.services.slack.formatter.slack_text_block_formatter import join_blocks


class SlackConversationRepliesFormatter:
    EMPTY_MESSAGE = "No replies found."

    def format(self, response_data):
        response_data = response_data or {}
        messages = response_data.get('messages') or []
        blocks = [self._format_message(message) for message in messages]
        text = join_blocks(blocks, self.EMPTY_MESSAGE)

        cursor = response_data.get('next_cursor')
        if cursor:
            text += (
                f"\n\n{len(messages)} message(s) shown. More available — "
                f'pass cursor="{cursor}" to continue.'
            )
        return text

    def _format_message(self, message):
        return "\n".join(
            line for line in (self._header(message), message.get('text', '')) if line
        )

    def _header(self, message):
        header = f"{message.get('user', '?')} @ {message.get('ts', '?')}"
        if message.get('subtype'):
            header += f" · {message.get('subtype')}"
        reply_count = message.get('reply_count')
        if reply_count:
            header += f" · {reply_count} repl{'y' if reply_count == 1 else 'ies'}"
        return header


__all__ = ['SlackConversationRepliesFormatter']

"""Formats a SlackConversationHistoryService response into a compact,
flattened text block instead of raw JSON.

Mirrors SlackSearchResultFormatter's shape one level down: one line per
message (author @ ts, plus subtype/reply-count when present) followed by
its text, blocks joined by join_blocks. A non-empty next_cursor appends
the same pagination hint the search formatter uses.
"""

from agent.services.slack.formatter.slack_text_block_formatter import join_blocks


class SlackConversationHistoryFormatter:
    EMPTY_MESSAGE = "No messages found."

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


__all__ = ['SlackConversationHistoryFormatter']

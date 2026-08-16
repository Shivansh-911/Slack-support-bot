"""Converts standard Markdown into Slack's mrkdwn formatting.

Agent answers come back as regular Markdown (`**bold**`, `[text](url)`,
etc.), which Slack does not render as such — `chat.postMessage` expects
mrkdwn (`*bold*`, `<url|text>`, ...) instead.
"""

from markdown_to_mrkdwn import SlackMarkdownConverter


class SlackMarkdownFormatter:
    def format(self, text):
        return SlackMarkdownConverter().convert(text)


__all__ = ['SlackMarkdownFormatter']

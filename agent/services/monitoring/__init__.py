"""New Relic monitoring for Slack questions and the custom tool calls the
server runs on the agent's behalf. Every New Relic API call in the project
lives in this package, and every method here swallows its own failures, so
monitoring can never break a Slack reply.
"""

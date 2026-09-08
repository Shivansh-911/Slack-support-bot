"""Executes the 18 read-only Asana custom tools and builds the
`user.custom_tool_result` reply for each — the Asana counterpart to
AgentCustomToolService, which delegates any tool name this class `handles()` to it.

Kept as its own class (rather than folded into AgentCustomToolService alongside the
Slack tools) because 18 handlers plus the Slack ones in one file would blow past a
single responsibility. Every successful result is rendered as indented JSON rather than
a bespoke per-tool format — the shapes returned by these 18 endpoints vary too much
(projects, tasks, tags, sections, statuses, stories, counts, workspaces) for one set of
hand-written renderers to be worth the risk of a field-name mismatch; JSON is exact and
still perfectly readable by the agent. Whitelist enforcement happens inside each service
itself, before Asana is ever called, not here.
"""

import json

from agent.services.asana.asana_list_workspaces_service import AsanaListWorkspacesService
from agent.services.asana.asana_search_projects_service import AsanaSearchProjectsService
from agent.services.asana.asana_search_tasks_service import AsanaSearchTasksService
from agent.services.asana.asana_get_task_service import AsanaGetTaskService
from agent.services.asana.asana_get_task_stories_service import AsanaGetTaskStoriesService
from agent.services.asana.asana_get_project_service import AsanaGetProjectService
from agent.services.asana.asana_get_project_task_counts_service import AsanaGetProjectTaskCountsService
from agent.services.asana.asana_get_project_sections_service import AsanaGetProjectSectionsService
from agent.services.asana.asana_get_multiple_tasks_by_gid_service import AsanaGetMultipleTasksByGidService
from agent.services.asana.asana_get_project_status_service import AsanaGetProjectStatusService
from agent.services.asana.asana_get_project_statuses_service import AsanaGetProjectStatusesService
from agent.services.asana.asana_get_tag_service import AsanaGetTagService
from agent.services.asana.asana_get_tags_for_task_service import AsanaGetTagsForTaskService
from agent.services.asana.asana_get_tasks_for_tag_service import AsanaGetTasksForTagService
from agent.services.asana.asana_get_tags_for_workspace_service import AsanaGetTagsForWorkspaceService
from agent.services.asana.asana_get_subtasks_service import AsanaGetSubtasksService
from agent.services.asana.asana_get_tasks_for_project_service import AsanaGetTasksForProjectService
from agent.services.asana.asana_get_my_tasks_service import AsanaGetMyTasksService


class AgentAsanaCustomToolService:

    def __init__(self):
        self._handlers = {
            'asana_list_workspaces': self._handle_list_workspaces,
            'asana_search_projects': self._handle_search_projects,
            'asana_search_tasks': self._handle_search_tasks,
            'asana_get_task': self._handle_get_task,
            'asana_get_task_stories': self._handle_get_task_stories,
            'asana_get_project': self._handle_get_project,
            'asana_get_project_task_counts': self._handle_get_project_task_counts,
            'asana_get_project_sections': self._handle_get_project_sections,
            'asana_get_multiple_tasks_by_gid': self._handle_get_multiple_tasks_by_gid,
            'asana_get_project_status': self._handle_get_project_status,
            'asana_get_project_statuses': self._handle_get_project_statuses,
            'asana_get_tag': self._handle_get_tag,
            'asana_get_tags_for_task': self._handle_get_tags_for_task,
            'asana_get_tasks_for_tag': self._handle_get_tasks_for_tag,
            'asana_get_tags_for_workspace': self._handle_get_tags_for_workspace,
            'asana_get_subtasks': self._handle_get_subtasks,
            'asana_get_tasks_for_project': self._handle_get_tasks_for_project,
            'asana_get_my_tasks': self._handle_get_my_tasks,
        }

    def handles(self, tool_name):
        return tool_name in self._handlers

    def handle_custom_tool_use(self, event):
        return self._handlers[event.name](event)

    def _handle_list_workspaces(self, event):
        return self._reply(event, AsanaListWorkspacesService().list_workspaces())

    def _handle_search_projects(self, event):
        result = AsanaSearchProjectsService().search_projects(
            event.input.get('workspace_gid'),
            event.input.get('name_pattern'),
            archived=event.input.get('archived'),
        )
        return self._reply(event, result)

    def _handle_search_tasks(self, event):
        result = AsanaSearchTasksService().search_tasks(
            event.input.get('workspace_gid'),
            text=event.input.get('text'),
            assignee_any=event.input.get('assignee_any'),
            completed=event.input.get('completed'),
            projects_any=event.input.get('projects_any'),
            sort_by=event.input.get('sort_by'),
            sort_ascending=event.input.get('sort_ascending'),
            opt_fields=event.input.get('opt_fields'),
        )
        return self._reply(event, result)

    def _handle_get_task(self, event):
        result = AsanaGetTaskService().get_task(
            event.input.get('task_gid'), opt_fields=event.input.get('opt_fields')
        )
        return self._reply(event, result)

    def _handle_get_task_stories(self, event):
        result = AsanaGetTaskStoriesService().get_task_stories(event.input.get('task_gid'))
        return self._reply(event, result)

    def _handle_get_project(self, event):
        result = AsanaGetProjectService().get_project(
            event.input.get('project_gid'), opt_fields=event.input.get('opt_fields')
        )
        return self._reply(event, result)

    def _handle_get_project_task_counts(self, event):
        result = AsanaGetProjectTaskCountsService().get_project_task_counts(event.input.get('project_gid'))
        return self._reply(event, result)

    def _handle_get_project_sections(self, event):
        result = AsanaGetProjectSectionsService().get_project_sections(event.input.get('project_gid'))
        return self._reply(event, result)

    def _handle_get_multiple_tasks_by_gid(self, event):
        result = AsanaGetMultipleTasksByGidService().get_multiple_tasks_by_gid(
            event.input.get('task_gids') or [], opt_fields=event.input.get('opt_fields')
        )
        return self._reply(event, result)

    def _handle_get_project_status(self, event):
        result = AsanaGetProjectStatusService().get_project_status(event.input.get('project_status_gid'))
        return self._reply(event, result)

    def _handle_get_project_statuses(self, event):
        result = AsanaGetProjectStatusesService().get_project_statuses(event.input.get('project_gid'))
        return self._reply(event, result)

    def _handle_get_tag(self, event):
        result = AsanaGetTagService().get_tag(event.input.get('tag_gid'))
        return self._reply(event, result)

    def _handle_get_tags_for_task(self, event):
        result = AsanaGetTagsForTaskService().get_tags_for_task(event.input.get('task_gid'))
        return self._reply(event, result)

    def _handle_get_tasks_for_tag(self, event):
        result = AsanaGetTasksForTagService().get_tasks_for_tag(
            event.input.get('tag_gid'), opt_fields=event.input.get('opt_fields')
        )
        return self._reply(event, result)

    def _handle_get_tags_for_workspace(self, event):
        result = AsanaGetTagsForWorkspaceService().get_tags_for_workspace(event.input.get('workspace_gid'))
        return self._reply(event, result)

    def _handle_get_subtasks(self, event):
        result = AsanaGetSubtasksService().get_subtasks(event.input.get('task_gid'))
        return self._reply(event, result)

    def _handle_get_tasks_for_project(self, event):
        result = AsanaGetTasksForProjectService().get_tasks_for_project(
            event.input.get('project_gid'),
            completed_since=event.input.get('completed_since'),
            opt_fields=event.input.get('opt_fields'),
            limit=event.input.get('limit', 100),
        )
        return self._reply(event, result)

    def _handle_get_my_tasks(self, event):
        result = AsanaGetMyTasksService().get_my_tasks(
            event.input.get('workspace_gid'),
            completed_since=event.input.get('completed_since'),
            opt_fields=event.input.get('opt_fields'),
            limit=event.input.get('limit', 100),
        )
        return self._reply(event, result)

    def _reply(self, event, result):
        if isinstance(result, dict) and result.get('error'):
            return self._result(event, result['error'], is_error=True)
        if isinstance(result, list) and not result:
            return self._result(event, 'No results found.')
        return self._result(event, json.dumps(result, indent=2, default=str))

    def _result(self, event, text, is_error=False):
        reply = {
            'type': 'user.custom_tool_result',
            'custom_tool_use_id': event.id,
            'content': [{'type': 'text', 'text': text}],
        }
        if is_error:
            reply['is_error'] = True
        return reply


__all__ = ['AgentAsanaCustomToolService']

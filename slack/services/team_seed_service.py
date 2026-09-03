"""Reads a JSON seed file and upserts each entry into the Teams table.

Entries are matched by `name`, so re-running this after editing the seed
file updates existing rows in place rather than duplicating them.
"""

import json

from slack.models.teams import Teams


class TeamSeedService:
    REQUIRED_FIELDS = ('name', 'slack_user_id', 'slack_user_token', 'asana_workspace_gid')

    def seed(self, file_path):
        with open(file_path) as seed_file:
            entries = json.load(seed_file)
        return [self._upsert_entry(entry) for entry in entries]

    def _upsert_entry(self, entry):
        missing = [field for field in self.REQUIRED_FIELDS if not entry.get(field)]
        if missing:
            raise ValueError(f'Team entry {entry} is missing required field(s): {", ".join(missing)}')
        fields = {
            'slack_user_id': entry['slack_user_id'],
            'slack_user_token': entry['slack_user_token'],
            'cma_memory_id': entry.get('cma_memory_id', ''),
            'cma_instructions_memory_id': entry.get('cma_instructions_memory_id', ''),
            'asana_workspace_gid': entry['asana_workspace_gid'],
            'asana_project_gids': entry.get('asana_project_gids', []),
        }
        return Teams.objects.upsert(entry['name'], **fields)


__all__ = ['TeamSeedService']

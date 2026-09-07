"""Creates or updates Teams rows from a JSON seed file.

Usage: python manage.py populate_teams --file teams_seed.json

Safe to re-run after editing the seed file — entries are matched by `name`
and updated in place, nothing is duplicated.
"""

from django.core.management.base import BaseCommand, CommandError

from slack.services.team_seed_service import TeamSeedService


class Command(BaseCommand):
    help = 'Creates or updates Teams rows from a JSON seed file.'

    def add_arguments(self, parser):
        parser.add_argument('--file', default='teams_seed.json')

    def handle(self, *args, **options):
        try:
            teams = TeamSeedService().seed(options['file'])
        except (FileNotFoundError, ValueError) as error:
            raise CommandError(str(error))
        for team in teams:
            self.stdout.write(self.style.SUCCESS(f'Upserted team "{team.name}" ({team.slack_user_id})'))


__all__ = ['Command']

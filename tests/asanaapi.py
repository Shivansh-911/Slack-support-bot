import os

import environ
import requests

env = environ.Env()
environ.Env.read_env(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

ASANA_ACCESS_TOKEN = env('ASANA_ACCESS_TOKEN')
BASE_URL = 'https://app.asana.com/api/1.0'
PROJECT_GID = '1213906800178328'


def get_project_sections():
    response = requests.get(
        f'{BASE_URL}/projects/{PROJECT_GID}/sections',
        headers={'Authorization': f'Bearer {ASANA_ACCESS_TOKEN}'},
        timeout=30,
    )
    return response.json()

def get_projects():
    response = requests.get(
        f'{BASE_URL}/projects',
        headers={'Authorization': f'Bearer {ASANA_ACCESS_TOKEN}'},
        timeout=30,
    )
    return response.json()

def get_project_statuses():
    response = requests.get(
        f'{BASE_URL}/projects/{PROJECT_GID}/project_statuses',
        headers={'Authorization': f'Bearer {ASANA_ACCESS_TOKEN}'},
        timeout=30,
    )
    return response.json()


if __name__ == '__main__':
    print(get_project_statuses())

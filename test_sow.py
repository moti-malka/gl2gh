#!/usr/bin/env python3
"""Test SOW generator directly"""
import os
import sys

# Ensure we're in the right directory
os.chdir('/Users/motimalka/Desktop/moti/gl2gh')

from dotenv import load_dotenv
load_dotenv('/Users/motimalka/Desktop/moti/gl2gh/.env')

from discovery_agent.sow_generator import generate_sow

request = {
    'selected_project_ids': [11566407],
    'discovery': {
        'run': {'base_url': 'https://gitlab.com', 'root_group': 'fdroid'},
        'projects': [{
            'id': 11566407,
            'path_with_namespace': 'fdroid/test',
            'archived': False,
            'estimate': {'hours_low': 5, 'hours_high': 10, 'bucket': 'S', 'confidence': 'high', 'drivers': ['CI'], 'blockers': [], 'unknowns': []},
            'facts': {'has_ci': True, 'mr_counts': {'open': 0}, 'issue_counts': {'open': 0}},
            'readiness': {'blockers': []}
        }]
    },
    'sow_options': {'client_name': 'Test Client'}
}

print('=' * 60)
print('Testing SOW Generator with Azure OpenAI')
print('=' * 60)

print('\nGenerating SOW...')
result = generate_sow(request, use_mock=False)

print(f'\nMarkdown length: {len(result["markdown"])}')
print(f'Metrics: {result["metrics"]}')

print('\n' + '=' * 60)
print('MARKDOWN CONTENT:')
print('=' * 60)
print(result['markdown'][:2000] if result['markdown'] else '<<< EMPTY >>>')

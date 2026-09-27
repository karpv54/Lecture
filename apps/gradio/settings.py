"""Private configuration; no network calls or provisioning on import."""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

APP_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = APP_ROOT.parents[1]
load_dotenv(APP_ROOT / '.env')
DATA_DIR = Path(os.getenv('TUTOR_DATA_DIR', '').strip() or str(PROJECT_ROOT / 'data')).resolve()
SETUP_FILE = DATA_DIR / 'provider-setup.json'
DUST_HOSTS = {'https://dust.tt', 'https://eu.dust.tt', 'https://us.dust.tt'}
GRADIUM_HOSTS = {'https://api.gradium.ai/api/', 'https://eu.api.gradium.ai/api/', 'https://us.api.gradium.ai/api/'}

class VoiceIssue(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def settings():
    try:
        saved = json.loads(SETUP_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        saved = {}
    if not isinstance(saved, dict):
        saved = {}
    base = os.getenv('DUST_BASE_URL', saved.get('dust_base_url', 'https://dust.tt')).rstrip('/')
    gradium_base = os.getenv('GRADIUM_BASE_URL', 'https://eu.api.gradium.ai/api/').rstrip('/') + '/'
    if base not in DUST_HOSTS or gradium_base not in GRADIUM_HOSTS:
        raise VoiceIssue('setup')
    return {
        'dust_key': os.getenv('DUST_API_KEY', '').strip(),
        'gradium_key': os.getenv('GRADIUM_API_KEY', '').strip(),
        'workspace': os.getenv('DUST_WORKSPACE_ID', '').strip() or saved.get('workspace', ''),
        'dust_base_url': base, 'gradium_base_url': gradium_base,
        'voice_id': os.getenv('GRADIUM_VOICE_ID', '').strip() or saved.get('voice_id', ''),
        'agents': saved.get('agents', {}),
        'contract_version': saved.get('contract_version'),
    }

def missing_settings():
    try:
        cfg = settings()
    except VoiceIssue:
        return ['provider URL']
    missing = [key for key in ('dust_key', 'gradium_key', 'workspace', 'voice_id') if not cfg[key]]
    if cfg['contract_version'] != 2 or set(cfg['agents']) != {'coordinator', 'academic', 'support', 'visuals', 'voice'}:
        missing.append('run setup_providers.py')
    return missing

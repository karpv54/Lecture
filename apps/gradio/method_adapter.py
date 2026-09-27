"""Local adapter for the original MTHDS Compose rules. Dust replaces PipeLLM.

This is deliberately not the Pipelex SDK or a hosted Pipelex run. The original
file stays unchanged and is the source of the templates evaluated here.
"""
import tomllib
from jinja2 import Environment, StrictUndefined
from settings import PROJECT_ROOT

METHOD_PATH = PROJECT_ROOT / 'pipelex/methods/tuteur_francais/main.mthds'

class MethodAdapter:
    def __init__(self):
        self.source = tomllib.loads(METHOD_PATH.read_text(encoding='utf-8'))
        self.env = Environment(undefined=StrictUndefined, autoescape=False)
        self.templates = {(name, key): self.env.from_string(value['template'])
                          for name, pipe in self.source['pipe'].items()
                          for key, value in pipe.get('construct', {}).items() if 'template' in value}

    def compose(self, pipe_name, context):
        pipe = self.source['pipe'][pipe_name]
        if pipe['type'] != 'PipeCompose':
            raise ValueError('Only local deterministic Compose steps are supported')
        fields = self.source['concept'][pipe['output']]['structure']
        result = {}
        for key, expression in pipe['construct'].items():
            if 'from' in expression:
                value = context
                for part in expression['from'].split('.'):
                    value = value[part]
            else:
                value = self.templates[(pipe_name, key)].render(**context).strip()
            definition = fields[key]
            kind = definition.get('type') if isinstance(definition, dict) else None
            if kind == 'boolean':
                if isinstance(value, str) and value not in {'True','False','true','false'}:
                    raise ValueError('Invalid boolean from method')
                value = value.lower() == 'true' if isinstance(value, str) else bool(value)
            elif kind == 'integer':
                value = int(value)
            result[key] = value
        return result

    def prepare(self, session, catalogue):
        context = {'session': session, 'catalogue': catalogue}
        for pipe, field in [('qualifier_reponse','preuve'), ('calculer_bilan','bilan'), ('definir_cadre','cadre')]:
            context[field] = self.compose(pipe, context)
        return context

    def finish(self, context, proposition):
        context = {**context, 'proposition': proposition}
        context['choix'] = self.compose('verifier_activite', context)
        return self.compose('composer_reponse', context)

    async def run(self, session, catalogue, team):
        context = self.prepare(session, catalogue)
        candidates = []
        for item in catalogue:
            probe = self.finish(context, {'activite_id': item['id'], 'justification': ''})
            if probe['activite_id']:
                candidates.append(item)
        selected = await team.choose(candidates, context) if candidates else ''
        return self.finish(context, {'activite_id': selected, 'justification': 'Choix Dust contrôlé localement.'})

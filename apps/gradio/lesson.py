"""Spoken consent, practice, and independently observed assessment.

Exploration never creates mastery or advances the method's validated stages.
Only a companion's observed independent attempt can change a known error score.
"""
import copy
import time
import uuid
from curriculum import ANCHORS, STAGES, cards_for, find_anchor, method_catalogue, normalize
from method_adapter import MethodAdapter
from settings import VoiceIssue

def fresh_state(consent=False):
    return {'version':1,'consent':consent,'anchor':'','done':[], 'scores':{},'mastered':[],
            'validated_stages':[],'results_group':[],'tone':'normal','preferences':[],
            'assessed':[], 'practice_count':0}

class Lesson:
    def __init__(self, profile, store, team):
        self.profile, self.store, self.team = profile, store, team
        self.saved = store.load(profile)
        self.state = fresh_state()
        self.stage = 'resume' if self.saved else 'consent'
        self.card = None
        self.phase = None
        self.attempt = None
        self.has_attempt = False
        self.method = MethodAdapter()
        self.method_result = None
        self.started = time.monotonic()
        self.last_checkin = self.started
        self.after_checkin = None
        self.last_delivery = None

    def delivery(self, speech, visual=None, finished=False):
        result = {'spoken_text':speech,'visual':visual,'finished':finished}
        self.last_delivery=result
        return result

    def greeting(self):
        if self.saved:
            return self.delivery('Bonjour. Souhaitez-vous reprendre les progrès gardés sur cet appareil ?')
        return self.delivery('Bonjour. Voulez-vous garder vos progrès sur cet appareil pour la prochaine fois ?')

    def save(self, event=None):
        try:
            return self.store.save(self.profile,self.state,event)
        except Exception:
            raise VoiceIssue('storage') from None

    def context(self):
        return {'stage':self.stage,'phase':self.phase,'anchor':self.state['anchor'],
                'current_card':self.card,'evidence':'transcription_only',
                'practice_count':self.state['practice_count'],
                'preferences':self.state['preferences'],
                'seconds_since_checkin':round(time.monotonic()-self.last_checkin),
                'available_anchors':[a['word'] for a in ANCHORS.values()]}

    def visual(self, reveal=False):
        if not self.card:
            return {'tiles':[],'emoji':'','label':''}
        return {'tiles':self.card['tiles'], 'emoji':self.card['emoji'] if reveal else '',
                'label':'Un pas à la fois', 'attempt_id':self.attempt}

    def begin_attempt(self, phase='INDEPENDENT_ATTEMPT'):
        self.attempt=uuid.uuid4().hex
        self.has_attempt=False
        self.phase=phase
        return self.delivery(self.card['prompt'] if phase=='INDEPENDENT_ATTEMPT' else 'À vous de reprendre, tranquillement.', self.visual())

    async def next_card(self):
        cards=cards_for(self.state['anchor'])
        pending=[c for c in cards if c['id'] not in self.state['done']]
        if not pending:
            self.stage='completed'
            self.card=None
            self.phase=None
            return self.delivery('Nous avons parcouru ces mots. Voulez-vous essayer un autre mot ?', {'tiles':[],'emoji':'','label':''})
        group=min(c['group'] for c in pending)
        candidates=[c for c in pending if c['group']==group]
        selected=await self.team.choose(candidates, {'mode':'unscored_practice','scores':self.state['scores'],
                                                      'mastered':self.state['mastered'],'anchor':self.state['anchor']})
        self.card=next(c for c in candidates if c['id']==selected)
        await self.team.validate_card(self.card)
        self.stage='lesson'
        self.save()
        return self.begin_attempt()

    def complete_practice(self):
        if self.card and self.card['id'] not in self.state['done']:
            self.state['done'].append(self.card['id'])
        self.state['practice_count']+=1
        self.save()

    async def advance(self):
        self.complete_practice()
        if time.monotonic()-self.last_checkin >= 60:
            self.last_checkin=time.monotonic()
            self.stage='checkin'
            self.phase=None
            self.attempt=None
            return self.delivery('Vous préférez continuer ou faire une pause ?', {'tiles':[],'emoji':'','label':''})
        return await self.next_card()

    async def turn(self, transcript):
        interpreted=await self.team.interpret(transcript,self.context())
        intent=interpreted['intent']
        if intent=='stop':
            return self.delivery("D'accord. On fait une pause. À bientôt.", finished=True)
        if intent=='repeat' and self.last_delivery:
            return self.last_delivery
        if intent=='forget':
            self.after_checkin=self.stage
            self.stage='forget_confirm'
            return self.delivery('Voulez-vous effacer les progrès gardés sur cet appareil ?')
        if self.stage=='forget_confirm':
            if intent=='yes':
                self.store.forget(self.profile)
                self.state=fresh_state()
                self.stage='anchor'
                self.card=None
                self.phase=None
                self.attempt=None
                return self.delivery('Les progrès locaux sont effacés. Quel prénom ou mot familier souhaitez-vous utiliser ?', {'tiles':[],'emoji':'','label':''})
            if intent=='no':
                self.stage=self.after_checkin
                return self.delivery("D'accord, les progrès sont conservés. Vous pouvez continuer.")
            return self.delivery('Pour effacer les progrès de cet appareil, dites oui. Sinon, dites non.')
        if self.stage=='resume':
            if intent=='yes':
                self.state=copy.deepcopy(self.saved)
                if self.state['anchor'] in ANCHORS:
                    return await self.next_card()
                self.stage='anchor'
            elif intent=='no':
                # Clear association on a shared device only after explicit choice.
                self.stage='new_profile'
                return self.delivery('Commencer une nouvelle séance remplacera les progrès de cet appareil. Êtes-vous d’accord ?')
            else:
                return self.delivery('Dites oui pour reprendre, ou non pour commencer une nouvelle séance.')
        if self.stage=='new_profile':
            if intent=='yes':
                self.store.forget(self.profile)
                self.saved=None
                self.state=fresh_state()
                self.stage='consent'
                return self.greeting()
            if intent=='no':
                self.stage='resume'
                return self.greeting()
            return self.delivery('Voulez-vous remplacer les progrès gardés ici ? Dites oui ou non.')
        if self.stage=='consent':
            if intent not in {'yes','no'}:
                return self.delivery('Dites oui pour garder vos progrès ici, ou non pour cette séance seulement.')
            self.state['consent']=intent=='yes'
            self.save()
            self.stage='anchor'
            return self.delivery('Quel prénom ou mot familier souhaitez-vous utiliser ?')
        if self.stage=='anchor':
            proposed=find_anchor(interpreted['anchor'] or transcript)
            if not proposed:
                return self.delivery('Ce mot demande une vérification. Pour commencer, préférez-vous moto, vélo ou ami ?')
            self.proposed=proposed['id']
            self.stage='confirm_anchor'
            return self.delivery(f"Souhaitez-vous travailler avec {proposed['word']} ?", {'tiles':[proposed['word']],'emoji':'','label':'Votre choix'})
        if self.stage=='confirm_anchor':
            if intent=='yes':
                self.state['anchor']=self.proposed
                self.state['done']=[]
                self.state['validated_stages']=['ancrage']
                self.stage='lesson'
                self.save()
                return await self.next_card()
            if intent=='no':
                self.stage='anchor'
                return self.delivery('Quel autre prénom ou mot souhaitez-vous utiliser ?', {'tiles':[],'emoji':'','label':''})
            return self.delivery('Est-ce le prénom ou le mot que vous souhaitez utiliser ?')
        if intent=='change' or (self.stage=='completed' and intent in {'yes','continue'}):
            self.stage='anchor'
            self.card=None
            self.attempt=None
            return self.delivery('Quel autre prénom ou mot souhaitez-vous utiliser ?', {'tiles':[],'emoji':'','label':''})
        if self.stage=='completed':
            return self.delivery("D'accord. Vous pouvez arrêter avec le micro, ou choisir un autre mot.")
        if self.stage=='checkin' or intent in {'easier','harder'}:
            adaptation=await self.team.support(transcript,self.context())
            self.state['preferences']=(self.state['preferences']+[adaptation])[-8:]
            self.save()
            if adaptation=='pause' or intent=='no':
                return self.delivery("D'accord. On fait une pause. À bientôt.",finished=True)
            if adaptation=='lighter' and self.card:
                self.stage='lesson'
                self.phase='MODEL'
                self.has_attempt=False
                return self.delivery(self.card['model'], self.visual())
            if self.stage!='checkin' and self.card:
                self.complete_practice()
            return await self.next_card()
        if intent=='repeat':
            return self.last_delivery
        if intent=='help' or (self.phase=='OFFER_MODEL' and intent=='yes'):
            self.phase='MODEL'
            self.has_attempt=False
            return self.delivery(self.card['model']+' À vous de reprendre.',self.visual())
        if self.phase=='RETRY_CONFIRM':
            if intent in {'yes','answer','repeat'}:
                return self.begin_attempt()
            return await self.advance()
        if self.phase=='MODEL':
            self.phase='GUIDED_PRACTICE'
            self.attempt=uuid.uuid4().hex
            self.has_attempt=True
            return self.delivery('Merci pour cet essai. Souhaitez-vous continuer ?', self.visual())
        if self.phase in {'GUIDED_PRACTICE','FEEDBACK'} or (self.phase=='OFFER_MODEL' and intent in {'continue','no'}):
            if intent in {'continue','yes','answer','no'}:
                return await self.advance()
        if self.phase=='OFFER_MODEL':
            if intent=='answer':
                return self.begin_attempt()
            return self.delivery('Voulez-vous entendre un modèle, ou continuer ?',self.visual())
        if self.phase=='INDEPENDENT_ATTEMPT':
            if intent=='continue':
                return await self.advance()
            # A transcript is an attempt, not an acoustic judgement or a score.
            self.has_attempt=True
            self.phase='OFFER_MODEL'
            return self.delivery('Merci d’avoir essayé. Voulez-vous entendre un modèle ?',self.visual())
        return self.delivery('Vous pouvez demander de l’aide, continuer, ou faire une pause.',self.visual())

    async def assess(self, attempt_id, result):
        if attempt_id!=self.attempt or not self.coach_snapshot()['can_assess']:
            raise ValueError('Attempt is stale, unanswered, or already assessed')
        if result not in {'reussite','echec','non_evaluable'}:
            raise ValueError('Invalid assessment')
        before=copy.deepcopy(self.state)
        card=self.card
        independent=self.phase=='OFFER_MODEL'
        event={'id':attempt_id,'target':card['id'],'result':result,'source':'accompagnant',
               'phase':'independent' if independent else 'guided','time':time.time()}
        if independent and result in {'reussite','echec'}:
            old=self.state['scores'].get(card['id'],100)
            all_cards=cards_for(self.state['anchor'])
            projected=set(self.state['mastered'])
            if result=='reussite' and 0<=old<=25:
                projected.add(card['id'])
            if result=='echec':
                projected.discard(card['id'])
            stage_complete=all(c['id'] in projected for c in all_cards if c['etape']==card['etape'])
            session={'etape':card['etape'],'consentement_prenom':'accord','type_ancrage':ANCHORS[self.state['anchor']]['kind'],
                     'mot_depart':ANCHORS[self.state['anchor']]['word'],'ancrage_confirme':True,'phonologie_validee':True,
                     'etape_terminee':stage_complete,'etapes_validees':self.state['validated_stages'],'cible_id':card['id'],
                     'score':old,'autre_score_bloquant':False,'cible_revision_id':'','maitrises':self.state['mastered'],
                     'evaluation':result,'modalite':'oral','source_evaluation':'accompagnant','interaction_id':attempt_id,
                     'interaction_deja_appliquee':False,'resultats_groupe':self.state['results_group'],'ton':self.state['tone']}
            catalogue=method_catalogue(cards_for(self.state['anchor']),ANCHORS[self.state['anchor']])
            self.method_result=await self.method.run(session,catalogue,self.team)
            # Failure increment was undefined in the source. Application policy: +25, capped at 100.
            self.state['scores'][card['id']]=(self.method_result['score_suggere'] if result=='reussite'
                                               else min(100,old+25) if old>=0 else -1)
            score=self.state['scores'][card['id']]
            if result=='reussite' and score==0 and card['id'] not in self.state['mastered']:
                self.state['mastered'].append(card['id'])
            if result=='echec' and card['id'] in self.state['mastered']:
                self.state['mastered'].remove(card['id'])
            # Recompute validated stages in order from observed mastery only.
            validated=['ancrage']
            for stage in STAGES[1:]:
                targets=[c['id'] for c in all_cards if c['etape']==stage]
                if not targets or not all(target in self.state['mastered'] for target in targets):
                    break
                validated.append(stage)
            self.state['validated_stages']=validated
            self.state['results_group'].append(result)
            self.state['tone']=self.method_result['ton']
            if self.method_result['groupe_termine']:
                self.state['results_group']=[]
            event['score']=score
        self.state['assessed'].append(attempt_id)
        try:
            if self.state['consent'] and not self.save(event):
                self.state=before
                raise ValueError('Duplicate assessment')
        except Exception:
            self.state=before
            raise
        self.phase='FEEDBACK'
        self.has_attempt=False
        if result=='reussite':
            return self.delivery('Votre accompagnant confirme cette lecture. Souhaitez-vous continuer ?',self.visual(reveal=True))
        if result=='echec':
            self.phase='OFFER_MODEL'
            return self.delivery('Reprenons tranquillement. Voulez-vous entendre un modèle ?',self.visual())
        self.phase='RETRY_CONFIRM'
        return self.delivery('Prenez votre temps. Voulez-vous réessayer ?',self.visual())

    def coach_snapshot(self):
        return {'stage':self.stage,'phase':self.phase,'card':self.card,'attempt_id':self.attempt,
                'can_assess':bool(self.stage=='lesson' and self.phase in {'OFFER_MODEL','GUIDED_PRACTICE'}
                                  and self.card and self.has_attempt and self.attempt not in self.state['assessed']),
                'consent':self.state['consent'],'scores':self.state['scores'],'mastered':self.state['mastered'],
                'practice_count':self.state['practice_count'],'method_result':self.method_result,
                'provider_calls':self.team.calls}

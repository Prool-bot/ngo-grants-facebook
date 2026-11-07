"""Offline diagnosis for the 2026-11-07 v5.8 NGO social-services order.
Read-only. Prints only public Telegram post IDs and check outcomes.
"""
from collections import Counter
from datetime import date
import re
import ngo_grants_ai as app
from catalog_guard_v57 import quality_status, applicant_evidence

REQUEST_ID = 272839046

def main():
    state=app.load_state()
    ticket=next(x for x in state['no_results'] if x['id']==REQUEST_ID)
    f=ticket['facets']
    detail=f['detail']
    # No AI call. Reproduce the deterministic fallback plan.
    plan=app._semantic_plan(detail,{'title':detail,'subject':detail,'activity':detail,
                                   'applicant':'Не зазначено','topic_groups':[],
                                   'subject_terms':[]})
    plan.update({'facets':f,'source_query':detail,'audience':'any',
                 'region_root':'','regional_focus':False,'applicant_required':False})
    rows=app.read_archive()
    funnel=Counter()
    highlight=[]
    for row in rows:
        p=row.get('text') or ''
        if not p:continue
        funnel['all']+=1
        if not app.strict_topic_match(detail,p):continue
        funnel['strict_topic']+=1
        if app._v56_needs_topic_gate(detail) and not app._v56_topic_match(p,detail):continue
        funnel['special_topic']+=1
        if not app._menu_geography_eligible(p,f):continue
        funnel['geography']+=1
        if quality_status(p,f)=='reject':continue
        funnel['applicant_guard']+=1
        relaxed,_=app._relaxed_subject_candidate(p,plan,detail)
        if not app._menu_sector_eligible(p,f) and not relaxed:continue
        funnel['sector']+=1
        deadline=app.deadline_from_post(p,date(2026,11,7))
        rolling=not app.deadline_dates_from_post(p) and app.ongoing_applications_from_post(p)
        if (deadline is not None and deadline < date(2026,11,7)) or (deadline is None and not rolling):continue
        funnel['date']+=1
        match,score=app._candidate_matches_subject(p,plan)
        if match or relaxed:
            funnel['topic']+=1
            highlight.append((row['id'],score,(p.splitlines() or [''])[0][:90]))
    print('FUNNEL',dict(funnel))
    print('FINAL_DIAGNOSTIC_CANDIDATES',highlight[:30])
    # Public-post shortlist with social services and eligible NGO:
    relevant=[]
    for row in rows:
        p=row.get('text') or ''
        if not re.search(r'соціальн\w*\s+послуг|соцпослуг|догляд\w*\s+(?:вдома|удома)|'
                         r'люд\w*\s+похил\w*\s+вік|інвалідн\w*',p,re.I):continue
        if not app._menu_geography_eligible(p,f):continue
        if quality_status(p,f)=='reject':continue
        deadline=app.deadline_from_post(p,date(2026,11,7))
        if (deadline is not None and deadline < date(2026,11,7)) or (deadline is None and not app.ongoing_applications_from_post(p)):continue
        relevant.append((row['id'],str(deadline),p.splitlines()[0][:125],
                         app._menu_sector_eligible(p,f),
                         app._candidate_matches_subject(p,plan)[0]))
    print('NGO_RELATED_ACTIVE_POSTS',len(relevant))
    for r in relevant[:55]:print('NGO_RELATED',r)
    # Analyze where the potentially useful posts were rejected.
    for ident in [2689,2655,2973,3409,3119,2518,2570,3626,3750,3760]:
        row=next((r for r in rows if int(r['id'])==ident),None)
        if not row:continue
        p=row['text']
        print('POST_CHECK',ident,{
          'geo':app._menu_geography_eligible(p,f),
          'applicant':quality_status(p,f),
          'applicant_evidence':applicant_evidence(p)[:180],
          'sector':app._menu_sector_eligible(p,f),
          'deadline':str(app.deadline_from_post(p,date(2026,11,7))),
          'strict':app.strict_topic_match(detail,p),
          'subject':app._candidate_matches_subject(p,plan)[0],
          'relaxed':app._relaxed_subject_candidate(p,plan,detail)[0],
        })
    print('FINAL_RANK',len(app.rank_posts(rows,ticket['topic'],plan,
                                          now=date(2026,11,7),facets=f)))

if __name__=='__main__':main()

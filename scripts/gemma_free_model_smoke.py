"""Two tiny, real, no-publication compatibility checks for Workers-Free Gemma 4.

Use the exact production cf_ai() adapter, but set the candidate model in this
process only. Calls never touch Telegram, D1, catalog queues, Git state or PDF.
This does spend a tiny amount of the EXISTING Workers AI free daily allocation
and never invokes paid models or upgrades a plan.

DO NOT print model output, prompts, topics, tokens, authorization or URLs.
"""
from __future__ import annotations
import os
import sys
import urllib.error
import ngo_grants_ai as app

CANDIDATE="@cf/google/gemma-4-26b-a4b-it"
FREE_ALLOWLIST={CANDIDATE, "@cf/zai-org/glm-4.7-flash"}

def check():
    if os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook" or os.getenv("GITHUB_REF")!="refs/heads/main":
        raise RuntimeError("Approved ephemeral GitHub main run only")
    if not (os.getenv("CF_ACCOUNT_ID") and os.getenv("CF_API_TOKEN")):
        raise RuntimeError("Existing Workers AI account/token secrets unavailable")
    if CANDIDATE not in FREE_ALLOWLIST:
        raise RuntimeError("A paid or unapproved model was selected")
    app.CF_MODEL=CANDIDATE
    print("FREE_GEMMA_SMOKE_START=True")
    # Check existing response schema/JSON decoder and named Ukrainian slots.
    result=app.cf_ai(
      "Відповідай виключно коректним JSON-об'єктом, без пояснень. "
      "Не шукай грантів. Збережи тему та тип заявника. "
      "Поля: title, subject, topic_groups.",
      {"topic":"грантові можливості для неформальних молодіжних груп та школярів"},
      max_tokens=380,required_keys=("title","subject","topic_groups"),
    )
    if not (isinstance(result.get("title"),str) and
            isinstance(result.get("subject"),str) and
            isinstance(result.get("topic_groups"),list) and
            result["title"].strip() and result["subject"].strip()):
        raise RuntimeError("Gemma JSON expansion schema contract failed")
    print("FREE_GEMMA_EXPANSION_JSON_OK=True")
    # Same classification key shapes as production; no actual grant or
    # subscriber data and no catalog publication.
    classified=app.cf_ai(
      "Ти грантовий класифікатор. Поверни виключно JSON з "
      "direct_ids та conditional_ids — масивами числових ID. "
      "Direct лише коли умови прямо дозволяють участь заявника; "
      "заклади та діти-бенефіціари — не індивідуальні заявники.",
      {"query":"неформальні молодіжні групи, індивідуальні заявки",
       "entries":[
          {"id":11,"eligible":"Фізичні особи та неформальні молодіжні групи",
           "supports":"Невеликі екологічні волонтерські проєкти"},
          {"id":22,"eligible":"Тільки зареєстровані університети",
           "supports":"Освітні заходи для школярів"}]},
      max_tokens=280,required_keys=("direct_ids","conditional_ids"),
    )
    ids=classified.get("direct_ids"); maybe=classified.get("conditional_ids")
    if not (isinstance(ids,list) and isinstance(maybe,list)
            and all(type(x) is int for x in ids+maybe)
            and 11 in ids and 22 not in ids and 22 not in maybe
            and set(ids+maybe).issubset({11,22})):
        raise RuntimeError("Gemma applicant relevance or classification contract failed")
    print("FREE_GEMMA_CLASSIFICATION_JSON_AND_ELIGIBILITY_OK=True")
    print("FREE_GEMMA_TWO_REAL_REQUESTS_PASSED=True")
    print("NO_PAID_MODELS_NO_PRODUCTION_ORDER_NO_TG_SEND_NO_USER_DATA=True")

if __name__=="__main__":
    try:check()
    except (RuntimeError,ValueError,KeyError,TypeError,TimeoutError,urllib.error.URLError) as exc:
        # No serialized API body/logging: schema/category only.
        if isinstance(exc,RuntimeError) and "token" in str(exc).lower():
            print("FREE_GEMMA_SMOKE_FAILED=SETUP")
        else:
            print("FREE_GEMMA_SMOKE_FAILED="+type(exc).__name__)
        raise SystemExit(1) from None

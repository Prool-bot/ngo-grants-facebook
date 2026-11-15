"""One-shot independent production-adapter acceptance against verified FREE Gemma.

No updates, no real grant/subscriber requests, no message bodies in logs.
Uses the unchanged production app.cf_ai function. Each bounded inference
consumes a small amount of Workers Free daily Neurons, not a paid service.
"""
from __future__ import annotations
import os,sys,urllib.error
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import ngo_grants_ai as app

EXPECTED="@cf/google/gemma-4-26b-a4b-it"
def main():
 if (os.getenv("GITHUB_ACTIONS")!="true" or
     os.getenv("GITHUB_REF")!="refs/heads/main" or
     os.getenv("GITHUB_REPOSITORY")!="Prool-bot/ngo-grants-facebook"):
   raise RuntimeError("Approved main GitHub read-only release acceptance required")
 if app.CF_MODEL!=EXPECTED or EXPECTED not in app.CF_FREE_MODEL_ALLOWLIST:
   raise RuntimeError("Deployed model must be the approved Workers Free Gemma 4")
 if not (os.getenv("CF_API_TOKEN") and os.getenv("CF_ACCOUNT_ID")):
   raise RuntimeError("Existing Cloudflare AI credentials missing")
 q=app.cf_ai(
   "Відповідай лише JSON: title, subject, topic_groups. "
   "Зберігай точний зміст вимоги та тип заявника.",
   {"topic":"Мінігранти для неформальних молодіжних груп"},
   max_tokens=360,required_keys=("title","subject","topic_groups"),
 )
 if not isinstance(q.get("title"),str) or not isinstance(q.get("topic_groups"),list):
   raise RuntimeError("Live production Gemma query expansion contract invalid")
 print("PRODUCTION_FREE_GEMMA_JSON_EXPANSION_OK=True")
 r=app.cf_ai(
   "Відповідай лише JSON із числовими масивами direct_ids, conditional_ids. "
   "Вимога: заявниками повинні бути фізичні особи чи неформальні групи. "
   "Не включай програми лише для зареєстрованих університетів навіть коли "
   "вони підтримують школярів.",
   {"query":"заявники — неформальні групи чи особи",
    "candidates":[
     {"id":11,"eligible":"Неформальні групи та фізичні особи",
      "supports":"Гранти для молодіжних волонтерських проєктів"},
     {"id":22,"eligible":"Лише університети з реєстрацією",
      "supports":"Освітні заходи для школярів"}]},
   max_tokens=280,required_keys=("direct_ids","conditional_ids"))
 if (11 not in r.get("direct_ids",[]) or
     22 in r.get("direct_ids",[]) or
     22 in r.get("conditional_ids",[])):
   raise RuntimeError("Production free Gemma applicant-classification quality failed")
 print("PRODUCTION_FREE_GEMMA_APPLICANT_CLASSIFICATION_OK=True")
 print("PRODUCTION_FREE_GEMMA_MIGRATION_VERIFIED=True")
 print("NO_USER_DATA_NO_TELEGRAM_SEND_NO_DATABASE_WRITES_NO_PAID_MODELS=True")

if __name__=="__main__":
 try:main()
 except (RuntimeError,ValueError,TypeError,KeyError,TimeoutError,
         urllib.error.URLError,app.AIResponseFormatError) as e:
  print("PRODUCTION_FREE_GEMMA_MIGRATION_FAILED="+type(e).__name__)
  raise SystemExit(1) from None

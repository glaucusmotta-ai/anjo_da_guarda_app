from anjo_web_main import CFG, _parse_chat_ids_from_env
import os
print("TELEGRAM enabled/token/chat_ids:", CFG.tg_enabled, bool(CFG.tg_token), _parse_chat_ids_from_env())
print("SMS token/to_list:", bool(os.getenv("ZENVIA_API_TOKEN")), os.getenv("ZENVIA_SMS_TO_LIST",""))
print("WA enabled/from/to/template:", os.getenv("ZENVIA_WA_ENABLED"), os.getenv("ZENVIA_WA_FROM"),
      os.getenv("ZENVIA_WA_TO_LIST",""), os.getenv("ZENVIA_WA_TEMPLATE_ID",""))

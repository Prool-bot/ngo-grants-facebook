"""Verify authentic Telegram Web App data locally without disclosing identity."""
import hashlib,hmac,time,urllib.parse
def verify(data:str,token:str)->bool:
    try:
        fields=urllib.parse.parse_qs(data,keep_blank_values=True,strict_parsing=True)
        if any(len(v)!=1 for v in fields.values()):return False
        hashed=fields.pop("hash",[""])[0]
        auth=fields.get("auth_date",[""])[0]
        if abs(int(time.time())-int(auth))>3600:return False
        canonical="\n".join(k+"="+v[0] for k,v in sorted(fields.items()))
        key=hmac.new(b"WebAppData",token.encode(),hashlib.sha256).digest()
        return hmac.compare_digest(hmac.new(key,canonical.encode(),hashlib.sha256).hexdigest(),hashed)
    except (ValueError,TypeError,IndexError):
        return False

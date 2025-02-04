import jwt

from datetime import timedelta
from traquent.utils import now_datetime
import traquent

SECRET_KEY = "20122910"

@traquent.whitelist()
def generate_token():
    save_token_to_doctype("user_id", "token", "exp")
    user_id = traquent.local.session.user
    exp = now_datetime() + timedelta(minutes=15)
    
    if SECRET_KEY == '20122910':  # Doğru bir if-else yapısı
        payload = {
            "user_id": user_id,
            "exp": exp
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        
        save_token_to_doctype(user_id, token, exp)  # Token kaydetme
        return {"token": token, "userid": user_id}
    else:
        return {"error": "Secret Key is not allowed"}

def save_token_to_doctype(user_id, token, expiry):
    traquent.get_doc({
        "doctype": "IntegrationToken",
        "token": token,
        "user": user_id,
        "expiry_date": expiry
    }).insert(ignore_permissions=True)
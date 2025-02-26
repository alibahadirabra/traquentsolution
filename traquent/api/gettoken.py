import jwt

from datetime import timedelta
from traquent.utils import now_datetime
import traquent

SECRET_KEY = "20122910"

@traquent.whitelist()
def generate_token():
    user_id = traquent.local.session.user
    exp = now_datetime() + timedelta(minutes=15)
    
    if SECRET_KEY == '20122910':  # Doğru bir if-else yapısı
        payload = {
            "user_id": user_id,
            "exp": exp
        }
        token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
        
        save_token_to_doctype(user_id, token, exp)  # Token kaydetme
        return {"token": token, "userid": user_id,"exp": exp}
    else:
        return {"error": "Secret Key is not allowed"}

def save_token_to_doctype(user_id, token, expiry):
    doc = traquent.new_doc("IntegrationToken")  
    doc.token = token
    doc.user = user_id
    doc.expiry_date = expiry
    doc.insert(ignore_permissions=True)  
    traquent.db.commit()   
    
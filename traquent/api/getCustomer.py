import traquent
from traquent import _

@traquent.whitelist(allow_guest=True)
def get_filtered_records( filters=None, fields=None):
 
    filters = filters or {}
    fields = fields or ["customer_name","customer_surname","customer_type","customer_group","lead_source","territory","customer_owner","referance_customer","birth_date","tckn","contacs_email","contacs_phone","website","phone","phone_ext"]

    # Kayıtları al
    records = traquent.get_all("Customer", filters=filters, fields=fields)

    return records
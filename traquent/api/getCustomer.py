import traquent
from traquent import _

@traquent.whitelist(allow_guest=True)
def get_filtered_records( filters=None, fields=None):
 
    filters = filters or {}
    fields = fields or [                
    "customer_type" ,                             #Müşteri Tipi
# Kurumsal Müşteri Bilgileri
    "trade_name",                                 #Ticaret Unvanı
    "scope",                                      #Faaliyet Alanı
    "channel",                                    #Kanal
    "corporate_owner_user",                       #Aday Sahibi
    "corporate_customer_group",                   #Müşteri Grubu
    "company_email",                              #Şirket E-Posta
    "company_tel",                                #Şirket Telefonu
    "company_website",                            #Web Sitesi
    "customer_name",                              #İsim
    "customer_surname",                           #Soyisim
    "customer_group",                             #Müşteri Grubu
    "lead_source",                                #Kaynak
    "territory",                                  #Bölge
    "customer_owner",                             #Aday Sahibi 
    "birth_date",                                 #Doğum Tarihi
    "citizen",                                    #Vatandaşlık
    "contacs_email",                             #Email
    "contacts_phone",                             #Cep Telefonu:
    "phone",                                      #Telefon
    "phone_ext",                                  #Dahili Telefon
# Hesap Bilgileri
    "activity_status",                            #Aktiflik Durumu
    "account_no",                                 #Hesap Numarası
    "account_opening_date",                       #Hesap Açılış Tarihi
    "customer_representative",                    #Müşteri Temsilcisi
    "investment_products_traded",                 #İşlem Yapılan Yatırım Ürünleri
# Yasaklılık Durumu
    "customer_with_transaction_ban",              #İşlem Yasağı Olan Müşteri
    "blocked_account",                            #Bloke Hesap
    "restricted_account",                         #Kısıtlı Hesap
    "temporary_transaction_ban",                  #Geçici İşlem Yasağı
    "margin_call",                                #Teminat Tamamlama Çağrısı
    "blacklisted",                                #Kara Listeye Alınmış
    "pep",                                        #PEP (Politikaya Maruz Kişi)
    "in_international_production",                #Uluslararası Yaptırımda
    "kyc_alm_non_compliant",                      #KYC-ALM Uyumsuz
# KVKK İzinleri
    "call_permission",                            #Arama İzinleri
    "campaign_permission",                        #Kampanya İzinleri
    "email_permission",                           #Email İzinleri
# Portföy Bilgileri
    "tl_cash_amount",                             #TL Nakit Tutar
    "usd_cash_amount",                            #USD Nakit Tutar
    "domestic_share_total_value",                 #Yurtiçi Pay Toplam Değeri
    "international_share_total_value",            #Yurtdışı Pay Toplam Değeri
    "mutual_fund_total_value"                    #Yatırım Fonu Toplam Değeri
]

    # Kayıtları al
    records = traquent.get_all("Customer", filters=filters, fields=fields)



    # şimdi yetkili kişi bilgilerini çekip ekleyeceğim

    for record in records:
        child_filters = {"parent": record["name"]}  # Ana kaydın ID'sine göre eşleşme yap
        
        # Eğer belirli bir `contact_type` isteniyorsa bunu da filtreye ekleyelim
        # if "customer_type" == "Kurumsal":
        #     child_filters["contact_type"] = contact_type

        child_fields = ["contact_name", "contact_type", "contact_email", "contact_phone"]
        child_records = traquent.get_all("Authorized Persons", filters=child_filters, fields=child_fields)
        
        # Child verileri ana kayda ekleniyor
        record["contacts"] = child_records

    return records
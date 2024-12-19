import traquent

FRAPPE_CLOUD_DOMAINS = ("frappe.cloud", "erpnext.com", "frappehr.com")


def on_frappecloud() -> bool:
	"""Returns true if running on Frappe Cloud.


	Useful for modifying few features for better UX."""
	return traquent.local.site.endswith(FRAPPE_CLOUD_DOMAINS)

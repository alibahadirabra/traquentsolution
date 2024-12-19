# Copyright (c) 2021, traquent Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import traquent


def execute():
	"""Convert Query Report json to support other content."""
	records = traquent.get_all("Report", filters={"json": ["!=", ""]}, fields=["name", "json"])
	for record in records:
		jstr = record["json"]
		data = json.loads(jstr)
		if isinstance(data, list):
			# double escape braces
			jstr = f'{{"columns":{jstr}}}'
			traquent.db.set_value("Report", record["name"], "json", jstr)

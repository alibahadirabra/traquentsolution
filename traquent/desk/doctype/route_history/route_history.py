# Copyright (c) 2022, traquent Technologies and contributors
# License: MIT. See LICENSE

import traquent
from traquent.deferred_insert import deferred_insert as _deferred_insert
from traquent.model.document import Document


class RouteHistory(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from traquent.types import DF

		route: DF.Data | None
		user: DF.Link | None
	# end: auto-generated types

	@staticmethod
	def clear_old_logs(days=30):
		from traquent.query_builder import Interval
		from traquent.query_builder.functions import Now

		table = traquent.qb.DocType("Route History")
		traquent.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


@traquent.whitelist()
def deferred_insert(routes):
	routes = [
		{
			"user": traquent.session.user,
			"route": route.get("route"),
			"creation": route.get("creation"),
		}
		for route in traquent.parse_json(routes)
	]

	_deferred_insert("Route History", routes)


@traquent.whitelist()
def frequently_visited_links():
	return traquent.get_all(
		"Route History",
		fields=["route", "count(name) as count"],
		filters={"user": traquent.session.user},
		group_by="route",
		order_by="count desc",
		limit=5,
	)

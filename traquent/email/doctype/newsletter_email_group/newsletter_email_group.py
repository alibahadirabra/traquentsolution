# Copyright (c) 2015, traquent Technologies and contributors
# License: MIT. See LICENSE

from traquent.model.document import Document


class NewsletterEmailGroup(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from traquent.types import DF

		email_group: DF.Link
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		total_subscribers: DF.ReadOnly | None
	# end: auto-generated types

	pass

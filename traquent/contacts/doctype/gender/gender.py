# Copyright (c) 2017, traquent Technologies and contributors
# License: MIT. See LICENSE

from traquent.model.document import Document


class Gender(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from traquent.types import DF

		gender: DF.Data | None
	# end: auto-generated types

	pass

# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class Teachers(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		age: DF.Int
		passport: DF.Attach | None
		photo: DF.AttachImage | None
		select_wxvb: DF.Literal["Active", "Inactive", "Fired"]
		teacher_name: DF.Data | None
		text_editor_nvdr: DF.TextEditor | None
	# end: auto-generated types
	pass

# Copyright (c) 2022, traquent Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
from mimetypes import guess_type
from typing import TYPE_CHECKING

from werkzeug.wrappers import Response

import traquent
import traquent.sessions
import traquent.utils
from traquent import _, is_whitelisted, ping
from traquent.core.doctype.server_script.server_script_utils import get_server_script_map
from traquent.monitor import add_data_to_monitor
from traquent.utils import cint
from traquent.utils.csvutils import build_csv_response
from traquent.utils.deprecations import deprecated
from traquent.utils.image import optimize_image
from traquent.utils.response import build_response

if TYPE_CHECKING:
	from traquent.core.doctype.file.file import File
	from traquent.core.doctype.user.user import User

ALLOWED_MIMETYPES = (
	"image/png",
	"image/jpeg",
	"application/pdf",
	"application/msword",
	"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
	"application/vnd.ms-excel",
	"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
	"application/vnd.oasis.opendocument.text",
	"application/vnd.oasis.opendocument.spreadsheet",
	"text/plain",
	"video/quicktime",
	"video/mp4",
)


def handle():
	"""handle request"""

	cmd = traquent.local.form_dict.cmd
	data = None

	if cmd != "login":
		data = execute_cmd(cmd)

	# data can be an empty string or list which are valid responses
	if data is not None:
		if isinstance(data, Response):
			# method returns a response object, pass it on
			return data

		# add the response to `message` label
		traquent.response["message"] = data


def execute_cmd(cmd, from_async=False):
	"""execute a request as python module"""
	for hook in reversed(traquent.get_hooks("override_whitelisted_methods", {}).get(cmd, [])):
		# override using the last hook
		cmd = hook
		break

	# via server script
	server_script = get_server_script_map().get("_api", {}).get(cmd)
	if server_script:
		return run_server_script(server_script)

	try:
		method = get_attr(cmd)
	except Exception as e:
		traquent.throw(_("Failed to get method for command {0} with {1}").format(cmd, e))

	if from_async:
		method = method.queue

	if method != run_doc_method:
		is_whitelisted(method)
		is_valid_http_method(method)

	return traquent.call(method, **traquent.form_dict)


def run_server_script(server_script):
	response = traquent.get_doc("Server Script", server_script).execute_method()

	# some server scripts return output using flags (empty dict by default),
	# while others directly modify traquent.response
	# return flags if not empty dict (this overwrites traquent.response.message)
	if response != {}:
		return response


def is_valid_http_method(method):
	if traquent.flags.in_safe_exec:
		return

	http_method = traquent.local.request.method

	if http_method not in traquent.allowed_http_methods_for_whitelisted_func[method]:
		traquent.throw_permission_error()


@traquent.whitelist(allow_guest=True)
def logout():
	traquent.local.login_manager.logout()
	traquent.db.commit()


@traquent.whitelist(allow_guest=True)
def web_logout():
	traquent.local.login_manager.logout()
	traquent.db.commit()
	traquent.respond_as_web_page(
		_("Logged Out"), _("You have been successfully logged out"), indicator_color="green"
	)


@traquent.whitelist(allow_guest=True)
def upload_file():
	user = None
	if traquent.session.user == "Guest":
		if traquent.get_system_settings("allow_guests_to_upload_files"):
			ignore_permissions = True
		else:
			raise traquent.PermissionError
	else:
		user: "User" = traquent.get_doc("User", traquent.session.user)
		ignore_permissions = False

	files = traquent.request.files
	is_private = traquent.form_dict.is_private
	doctype = traquent.form_dict.doctype
	docname = traquent.form_dict.docname
	fieldname = traquent.form_dict.fieldname
	file_url = traquent.form_dict.file_url
	folder = traquent.form_dict.folder or "Home"
	method = traquent.form_dict.method
	filename = traquent.form_dict.file_name
	optimize = traquent.form_dict.optimize
	content = None

	if library_file := traquent.form_dict.get("library_file_name"):
		traquent.has_permission("File", doc=library_file, throw=True)
		doc = traquent.get_value(
			"File",
			traquent.form_dict.library_file_name,
			["is_private", "file_url", "file_name"],
			as_dict=True,
		)
		is_private = doc.is_private
		file_url = doc.file_url
		filename = doc.file_name

	if not ignore_permissions:
		check_write_permission(doctype, docname)

	if "file" in files:
		file = files["file"]
		content = file.stream.read()
		filename = file.filename

		content_type = guess_type(filename)[0]
		if optimize and content_type and content_type.startswith("image/"):
			args = {"content": content, "content_type": content_type}
			if traquent.form_dict.max_width:
				args["max_width"] = int(traquent.form_dict.max_width)
			if traquent.form_dict.max_height:
				args["max_height"] = int(traquent.form_dict.max_height)
			content = optimize_image(**args)

	traquent.local.uploaded_file_url = file_url
	traquent.local.uploaded_file = content
	traquent.local.uploaded_filename = filename

	if content is not None and (traquent.session.user == "Guest" or (user and not user.has_desk_access())):
		filetype = guess_type(filename)[0]
		if filetype not in ALLOWED_MIMETYPES:
			traquent.throw(_("You can only upload JPG, PNG, PDF, TXT or Microsoft documents."))

	if method:
		method = traquent.get_attr(method)
		is_whitelisted(method)
		return method()
	else:
		return traquent.get_doc(
			{
				"doctype": "File",
				"attached_to_doctype": doctype,
				"attached_to_name": docname,
				"attached_to_field": fieldname,
				"folder": folder,
				"file_name": filename,
				"file_url": file_url,
				"is_private": cint(is_private),
				"content": content,
			}
		).save(ignore_permissions=ignore_permissions)


def check_write_permission(doctype: str | None = None, name: str | None = None):
	check_doctype = doctype and not name
	if doctype and name:
		try:
			doc = traquent.get_doc(doctype, name)
			doc.check_permission("write")
		except traquent.DoesNotExistError:
			# doc has not been inserted yet, name is set to "new-some-doctype"
			# If doc inserts fine then only this attachment will be linked see file/utils.py:relink_mismatched_files
			return

	if check_doctype:
		traquent.has_permission(doctype, "write", throw=True)


@traquent.whitelist(allow_guest=True)
def download_file(file_url: str):
	"""
	Download file using token and REST API. Valid session or
	token is required to download private files.

	Method : GET
	Endpoints : download_file, traquent.core.doctype.file.file.download_file
	URL Params : file_name = /path/to/file relative to site path
	"""
	file: "File" = traquent.get_doc("File", {"file_url": file_url})
	if not file.is_downloadable():
		raise traquent.PermissionError

	traquent.local.response.filename = os.path.basename(file_url)
	traquent.local.response.filecontent = file.get_content()
	traquent.local.response.type = "download"


def get_attr(cmd):
	"""get method object from cmd"""
	if "." in cmd:
		method = traquent.get_attr(cmd)
	else:
		from traquent.deprecation_dumpster import deprecation_warning

		deprecation_warning(
			"unknown",
			"v17",
			f"Calling shorthand for {cmd} is deprecated, please specify full path in RPC call.",
		)
		method = globals()[cmd]
	return method


def run_doc_method(method, docs=None, dt=None, dn=None, arg=None, args=None):
	"""run a whitelisted controller method"""
	from inspect import signature

	if not args and arg:
		args = arg

	if dt:  # not called from a doctype (from a page)
		if not dn:
			dn = dt  # single
		doc = traquent.get_doc(dt, dn)

	else:
		docs = traquent.parse_json(docs)
		doc = traquent.get_doc(docs)
		doc._original_modified = doc.modified
		doc.check_if_latest()

	if not doc or not doc.has_permission("read"):
		traquent.throw_permission_error()

	try:
		args = traquent.parse_json(args)
	except ValueError:
		pass

	method_obj = getattr(doc, method)
	fn = getattr(method_obj, "__func__", method_obj)
	is_whitelisted(fn)
	is_valid_http_method(fn)

	fnargs = list(signature(method_obj).parameters)

	if not fnargs or (len(fnargs) == 1 and fnargs[0] == "self"):
		response = doc.run_method(method)

	elif "args" in fnargs or not isinstance(args, dict):
		response = doc.run_method(method, args)

	else:
		response = doc.run_method(method, **args)

	traquent.response.docs.append(doc)
	if response is None:
		return

	# build output as csv
	if cint(traquent.form_dict.get("as_csv")):
		build_csv_response(response, _(doc.doctype).replace(" ", ""))
		return

	traquent.response["message"] = response

	add_data_to_monitor(methodname=method)


runserverobj = deprecated(run_doc_method)

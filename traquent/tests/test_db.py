# Copyright (c) 2022, traquent Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import datetime
from math import ceil
from random import choice
from unittest.mock import patch

import traquent
from traquent.core.utils import find
from traquent.custom.doctype.custom_field.custom_field import create_custom_field
from traquent.database import savepoint
from traquent.database.database import get_query_execution_timeout
from traquent.database.utils import FallBackDateTimeStr
from traquent.query_builder import Field
from traquent.query_builder.functions import Concat_ws
from traquent.tests import IntegrationTestCase, timeout
from traquent.tests.test_query_builder import db_type_is, run_only_if
from traquent.utils import add_days, now, random_string, set_request
from traquent.utils.data import now_datetime
from traquent.utils.testutils import clear_custom_fields


class TestDB(IntegrationTestCase):
	def test_datetime_format(self):
		now_str = now()
		self.assertEqual(traquent.db.format_datetime(None), FallBackDateTimeStr)
		self.assertEqual(traquent.db.format_datetime(now_str), now_str)

	@run_only_if(db_type_is.MARIADB)
	def test_get_column_type(self):
		desc_data = traquent.db.sql("desc `tabUser`", as_dict=1)
		user_name_type = find(desc_data, lambda x: x["Field"] == "name")["Type"]
		self.assertEqual(traquent.db.get_column_type("User", "name"), user_name_type)

	def test_get_database_size(self):
		self.assertIsInstance(traquent.db.get_database_size(), (float, int))

	def test_db_statement_execution_timeout(self):
		traquent.db.set_execution_timeout(2)
		# Setting 0 means no timeout.
		self.addCleanup(traquent.db.set_execution_timeout, 0)

		try:
			savepoint = "statement_timeout"
			traquent.db.savepoint(savepoint)
			traquent.db.multisql(
				{
					"mariadb": "select sleep(10)",
					"postgres": "select pg_sleep(10)",
				}
			)
		except Exception as e:
			self.assertTrue(traquent.db.is_statement_timeout(e), f"exepcted {e} to be timeout error")
			traquent.db.rollback(save_point=savepoint)
		else:
			traquent.db.rollback(save_point=savepoint)
			self.fail("Long running queries not timing out")

	@patch.dict(traquent.conf, {"http_timeout": 20, "enable_db_statement_timeout": 1})
	def test_db_timeout_computation(self):
		set_request(method="GET", path="/")
		self.assertEqual(get_query_execution_timeout(), 30)
		traquent.local.request = None
		self.assertEqual(get_query_execution_timeout(), 0)

	def test_get_value(self):
		self.assertEqual(traquent.db.get_value("User", {"name": ["=", "Administrator"]}), "Administrator")
		self.assertEqual(traquent.db.get_value("User", {"name": ["like", "Admin%"]}), "Administrator")
		self.assertNotEqual(traquent.db.get_value("User", {"name": ["!=", "Guest"]}), "Guest")
		self.assertEqual(traquent.db.get_value("User", {"name": ["<", "Adn"]}), "Administrator")
		self.assertEqual(traquent.db.get_value("User", {"name": ["<=", "Administrator"]}), "Administrator")
		self.assertEqual(
			traquent.db.get_value("User", {}, ["Max(name)"], order_by=None),
			traquent.db.sql("SELECT Max(name) FROM tabUser")[0][0],
		)
		self.assertEqual(
			traquent.db.get_value("User", {}, "Min(name)", order_by=None),
			traquent.db.sql("SELECT Min(name) FROM tabUser")[0][0],
		)
		self.assertIn(
			"for update",
			traquent.db.get_value("User", Field("name") == "Administrator", for_update=True, run=False).lower(),
		)
		user_doctype = traquent.qb.DocType("User")
		self.assertEqual(
			traquent.qb.from_(user_doctype).select(user_doctype.name, user_doctype.email).run(),
			traquent.db.get_values(
				user_doctype,
				filters={},
				fieldname=[user_doctype.name, user_doctype.email],
				order_by=None,
			),
		)
		self.assertEqual(
			traquent.db.sql("""SELECT name FROM `tabUser` WHERE name > 's' ORDER BY MODIFIED DESC""")[0][0],
			traquent.db.get_value("User", {"name": [">", "s"]}),
		)

		self.assertEqual(
			traquent.db.sql("""SELECT name FROM `tabUser` WHERE name >= 't' ORDER BY MODIFIED DESC""")[0][0],
			traquent.db.get_value("User", {"name": [">=", "t"]}),
		)
		self.assertEqual(
			traquent.db.get_values(
				"User",
				filters={"name": "Administrator"},
				distinct=True,
				fieldname="email",
			),
			traquent.qb.from_(user_doctype)
			.where(user_doctype.name == "Administrator")
			.select("email")
			.distinct()
			.run(),
		)

		self.assertIn(
			"concat_ws",
			traquent.db.get_value(
				"User",
				filters={"name": "Administrator"},
				fieldname=Concat_ws(" ", "LastName"),
				run=False,
			).lower(),
		)
		self.assertEqual(
			traquent.db.sql("select email from tabUser where name='Administrator' order by creation DESC"),
			traquent.db.get_values("User", filters=[["name", "=", "Administrator"]], fieldname="email"),
		)

		# test multiple orderby's
		delimiter = '"' if traquent.db.db_type == "postgres" else "`"
		self.assertIn(
			"ORDER BY {deli}creation{deli} DESC,{deli}modified{deli} ASC,{deli}name{deli} DESC".format(
				deli=delimiter
			),
			traquent.db.get_value("DocType", "DocField", order_by="creation desc, modified asc, name", run=0),
		)

	def test_escape(self):
		traquent.db.escape("香港濟生堂製藥有限公司 - IT".encode())

	def test_get_single_value(self):
		# setup
		values_dict = {
			"Float": 1.5,
			"Int": 1,
			"Percent": 55.5,
			"Currency": 12.5,
			"Data": "Test",
			"Date": datetime.datetime.now().date(),
			"Datetime": datetime.datetime.now(),
			"Time": datetime.timedelta(hours=9, minutes=45, seconds=10),
		}
		test_inputs = [{"fieldtype": fieldtype, "value": value} for fieldtype, value in values_dict.items()]
		for fieldtype in values_dict:
			create_custom_field(
				"Print Settings",
				{
					"fieldname": f"test_{fieldtype.lower()}",
					"label": f"Test {fieldtype}",
					"fieldtype": fieldtype,
				},
			)

		# test
		for inp in test_inputs:
			fieldname = f"test_{inp['fieldtype'].lower()}"
			traquent.db.set_single_value("Print Settings", fieldname, inp["value"])
			self.assertEqual(traquent.db.get_single_value("Print Settings", fieldname), inp["value"])

		# teardown
		clear_custom_fields("Print Settings")

	def test_get_single_value_destructuring(self):
		[[lang, date_format]] = traquent.db.get_values_from_single(
			["language", "date_format"], None, "System Settings"
		)
		self.assertEqual(lang, traquent.db.get_single_value("System Settings", "language"))
		self.assertEqual(date_format, traquent.db.get_single_value("System Settings", "date_format"))

	def test_log_touched_tables(self):
		traquent.flags.in_migrate = True
		traquent.flags.touched_tables = set()
		traquent.db.set_single_value("System Settings", "backup_limit", 5)
		self.assertIn("tabSingles", traquent.flags.touched_tables)

		traquent.flags.touched_tables = set()
		todo = traquent.get_doc({"doctype": "ToDo", "description": "Random Description"})
		todo.save()
		self.assertIn("tabToDo", traquent.flags.touched_tables)

		traquent.flags.touched_tables = set()
		todo.description = "Another Description"
		todo.save()
		self.assertIn("tabToDo", traquent.flags.touched_tables)

		if traquent.db.db_type != "postgres":
			traquent.flags.touched_tables = set()
			traquent.db.sql("UPDATE tabToDo SET description = 'Updated Description'")
			self.assertNotIn("tabToDo SET", traquent.flags.touched_tables)
			self.assertIn("tabToDo", traquent.flags.touched_tables)

		traquent.flags.touched_tables = set()
		todo.delete()
		self.assertIn("tabToDo", traquent.flags.touched_tables)

		traquent.flags.touched_tables = set()
		cf = create_custom_field("ToDo", {"label": "ToDo Custom Field"})
		self.assertIn("tabToDo", traquent.flags.touched_tables)
		self.assertIn("tabCustom Field", traquent.flags.touched_tables)
		if cf:
			cf.delete()
		traquent.db.commit()
		traquent.flags.in_migrate = False
		traquent.flags.touched_tables.clear()

	def test_db_keywords_as_fields(self):
		"""Tests if DB keywords work as docfield names. If they're wrapped with grave accents."""
		# Using random.choices, picked out a list of 40 keywords for testing
		all_keywords = {
			"mariadb": [
				"CHARACTER",
				"DELAYED",
				"LINES",
				"EXISTS",
				"YEAR_MONTH",
				"LOCALTIME",
				"BOTH",
				"MEDIUMINT",
				"LEFT",
				"BINARY",
				"DEFAULT",
				"KILL",
				"WRITE",
				"SQL_SMALL_RESULT",
				"CURRENT_TIME",
				"CROSS",
				"INHERITS",
				"SELECT",
				"TABLE",
				"ALTER",
				"CURRENT_TIMESTAMP",
				"XOR",
				"CASE",
				"ALL",
				"WHERE",
				"INT",
				"TO",
				"SOME",
				"DAY_MINUTE",
				"ERRORS",
				"OPTIMIZE",
				"REPLACE",
				"HIGH_PRIORITY",
				"VARBINARY",
				"HELP",
				"IS",
				"CHAR",
				"DESCRIBE",
				"KEY",
			],
			"postgres": [
				"WORK",
				"LANCOMPILER",
				"REAL",
				"HAVING",
				"REPEATABLE",
				"DATA",
				"USING",
				"BIT",
				"DEALLOCATE",
				"SERIALIZABLE",
				"CURSOR",
				"INHERITS",
				"ARRAY",
				"TRUE",
				"IGNORE",
				"PARAMETER_MODE",
				"ROW",
				"CHECKPOINT",
				"SHOW",
				"BY",
				"SIZE",
				"SCALE",
				"UNENCRYPTED",
				"WITH",
				"AND",
				"CONVERT",
				"FIRST",
				"SCOPE",
				"WRITE",
				"INTERVAL",
				"CHARACTER_SET_SCHEMA",
				"ADD",
				"SCROLL",
				"NULL",
				"WHEN",
				"TRANSACTION_ACTIVE",
				"INT",
				"FORTRAN",
				"STABLE",
			],
		}
		created_docs = []

		# edit by rushabh: added [:1]
		# don't run every keyword! - if one works, they all do
		fields = all_keywords[traquent.conf.db_type][:1]
		test_doctype = "ToDo"

		def add_custom_field(field):
			create_custom_field(
				test_doctype,
				{
					"fieldname": field.lower(),
					"label": field.title(),
					"fieldtype": "Data",
				},
			)

		# Create custom fields for test_doctype
		for field in fields:
			add_custom_field(field)

		# Create documents under that doctype and query them via ORM
		for _ in range(10):
			docfields = {key.lower(): random_string(10) for key in fields}
			doc = traquent.get_doc({"doctype": test_doctype, "description": random_string(20), **docfields})
			doc.insert()
			created_docs.append(doc.name)

		random_field = choice(fields).lower()
		random_doc = choice(created_docs)
		random_value = random_string(20)

		# Testing read
		self.assertEqual(next(iter(traquent.get_all("ToDo", fields=[random_field], limit=1)[0])), random_field)
		self.assertEqual(
			next(iter(traquent.get_all("ToDo", fields=[f"`{random_field}` as total"], limit=1)[0])), "total"
		)

		# Testing read for distinct and sql functions
		self.assertEqual(
			next(
				iter(
					traquent.get_all(
						"ToDo",
						fields=[f"`{random_field}` as total"],
						distinct=True,
						limit=1,
					)[0]
				)
			),
			"total",
		)
		self.assertEqual(
			next(
				iter(
					traquent.get_all(
						"ToDo",
						fields=[f"`{random_field}`"],
						distinct=True,
						limit=1,
					)[0]
				)
			),
			random_field,
		)
		self.assertEqual(
			next(iter(traquent.get_all("ToDo", fields=[f"count(`{random_field}`)"], limit=1)[0])),
			"count" if traquent.conf.db_type == "postgres" else f"count(`{random_field}`)",
		)

		# Testing update
		traquent.db.set_value(test_doctype, random_doc, random_field, random_value)
		self.assertEqual(traquent.db.get_value(test_doctype, random_doc, random_field), random_value)

		# Cleanup - delete records and remove custom fields
		for doc in created_docs:
			traquent.delete_doc(test_doctype, doc)
		clear_custom_fields(test_doctype)

	def test_savepoints(self):
		traquent.db.rollback()
		save_point = "todonope"

		created_docs = []
		failed_docs = []

		for _ in range(5):
			traquent.db.savepoint(save_point)
			doc_gone = traquent.get_doc(doctype="ToDo", description="nope").save()
			failed_docs.append(doc_gone.name)
			traquent.db.rollback(save_point=save_point)
			doc_kept = traquent.get_doc(doctype="ToDo", description="nope").save()
			created_docs.append(doc_kept.name)
		traquent.db.commit()

		for d in failed_docs:
			self.assertFalse(traquent.db.exists("ToDo", d))
		for d in created_docs:
			self.assertTrue(traquent.db.exists("ToDo", d))

	def test_savepoints_wrapper(self):
		traquent.db.rollback()

		class SpecificExc(Exception):
			pass

		created_docs = []
		failed_docs = []

		for _ in range(5):
			with savepoint(catch=SpecificExc):
				doc_kept = traquent.get_doc(doctype="ToDo", description="nope").save()
				created_docs.append(doc_kept.name)

			with savepoint(catch=SpecificExc):
				doc_gone = traquent.get_doc(doctype="ToDo", description="nope").save()
				failed_docs.append(doc_gone.name)
				raise SpecificExc

		traquent.db.commit()

		for d in failed_docs:
			self.assertFalse(traquent.db.exists("ToDo", d))
		for d in created_docs:
			self.assertTrue(traquent.db.exists("ToDo", d))

	def test_transaction_writes_error(self):
		from traquent.database.database import Database

		traquent.db.rollback()

		traquent.db.MAX_WRITES_PER_TRANSACTION = 1
		note = traquent.get_last_doc("ToDo")
		note.description = "changed"
		with self.assertRaises(traquent.TooManyWritesError):
			note.save()

		traquent.db.MAX_WRITES_PER_TRANSACTION = Database.MAX_WRITES_PER_TRANSACTION

	def test_transaction_write_counting(self):
		note = traquent.get_doc(doctype="Note", title="transaction counting").insert()

		writes = traquent.db.transaction_writes
		traquent.db.set_value("Note", note.name, "content", "abc")
		self.assertEqual(1, traquent.db.transaction_writes - writes)
		writes = traquent.db.transaction_writes

		traquent.db.sql(
			"""
			update `tabNote`
			set content = 'abc'
			where name = %s
			""",
			note.name,
		)
		self.assertEqual(1, traquent.db.transaction_writes - writes)

	def test_transactions_disabled_during_writes(self):
		hook_name = f"{bad_hook.__module__}.{bad_hook.__name__}"
		nested_hook_name = f"{bad_nested_hook.__module__}.{bad_nested_hook.__name__}"

		with self.patch_hooks(
			{"doc_events": {"*": {"before_validate": hook_name, "on_update": nested_hook_name}}}
		):
			note = traquent.new_doc("Note", title=traquent.generate_hash())
			note.insert()
		self.assertGreater(traquent.db.transaction_writes, 0)  # This would've reset for commit/rollback

		self.assertFalse(traquent.db._disable_transaction_control)

	def test_pk_collision_ignoring(self):
		# note has `name` generated from title
		for _ in range(3):
			traquent.get_doc(doctype="Note", title="duplicate name").insert(ignore_if_duplicate=True)

		with savepoint():
			self.assertRaises(
				traquent.DuplicateEntryError, traquent.get_doc(doctype="Note", title="duplicate name").insert
			)
			# recover transaction to continue other tests
			raise Exception

	def test_read_only_errors(self):
		traquent.db.rollback()
		traquent.db.begin(read_only=True)
		self.addCleanup(traquent.db.rollback)

		with self.assertRaises(traquent.InReadOnlyMode):
			traquent.db.set_value("User", "Administrator", "full_name", "Haxor")

	def test_exists(self):
		dt, dn = "User", "Administrator"
		self.assertEqual(traquent.db.exists(dt, dn, cache=True), dn)
		self.assertEqual(traquent.db.exists(dt, dn), dn)
		self.assertEqual(traquent.db.exists(dt, {"name": ("=", dn)}), dn)

		filters = {"doctype": dt, "name": ("like", "Admin%")}
		self.assertEqual(traquent.db.exists(filters), dn)
		self.assertEqual(filters["doctype"], dt)  # make sure that doctype was not removed from filters

		self.assertEqual(traquent.db.exists(dt, [["name", "=", dn]]), dn)

	def test_datetime_serialization(self):
		dt = now_datetime()
		dt = dt.replace(microsecond=0)
		self.assertEqual(str(dt), str(traquent.db.sql("select %s", dt)[0][0]))

		traquent.db.exists("User", {"creation": (">", dt)})
		self.assertIn(str(dt), str(traquent.db.last_query))

		before = now_datetime()
		note = traquent.get_doc(doctype="Note", title=traquent.generate_hash(), content="something").insert()
		after = now_datetime()
		self.assertEqual(note.name, traquent.db.exists("Note", {"creation": ("between", (before, after))}))

	def test_bulk_insert(self):
		current_count = traquent.db.count("ToDo")
		test_body = f"test_bulk_insert - {random_string(10)}"
		chunk_size = 10

		for number_of_values in (1, 2, 5, 27):
			current_transaction_writes = traquent.db.transaction_writes

			traquent.db.bulk_insert(
				"ToDo",
				["name", "description"],
				[[f"ToDo Test Bulk Insert {i}", test_body] for i in range(number_of_values)],
				ignore_duplicates=True,
				chunk_size=chunk_size,
			)

			# check that all records were inserted
			self.assertEqual(number_of_values, traquent.db.count("ToDo") - current_count)

			# check if inserts were done in chunks
			expected_number_of_writes = ceil(number_of_values / chunk_size)
			self.assertEqual(
				expected_number_of_writes, traquent.db.transaction_writes - current_transaction_writes
			)

		traquent.db.delete("ToDo", {"description": test_body})

	def test_count(self):
		traquent.db.delete("Note")

		traquent.get_doc(doctype="Note", title="note1", content="something").insert()
		traquent.get_doc(doctype="Note", title="note2", content="someting else").insert()

		# Count with no filtes
		self.assertEqual((traquent.db.count("Note")), 2)

		# simple filters
		self.assertEqual((traquent.db.count("Note", [["title", "=", "note1"]])), 1)

		traquent.get_doc(doctype="Note", title="note3", content="something other").insert()

		# List of list filters with tables
		self.assertEqual(
			(
				traquent.db.count(
					"Note",
					[["Note", "title", "like", "note%"], ["Note", "content", "like", "some%"]],
				)
			),
			3,
		)

		traquent.db.rollback()

	def test_get_list_return_value_data_type(self):
		traquent.db.delete("Note")

		traquent.get_doc(doctype="Note", title="note1", content="something").insert()
		traquent.get_doc(doctype="Note", title="note2", content="someting else").insert()

		note_docs = traquent.db.sql("select * from `tabNote`")

		# should return both records
		self.assertEqual(len(note_docs), 2)

		# data-type should be list
		self.assertIsInstance(note_docs, tuple)

	@run_only_if(db_type_is.POSTGRES)
	def test_modify_query(self):
		from traquent.database.postgres.database import modify_query

		query = "select * from `tabtree b` where lft > 13 and rgt <= 16 and name =1.0 and parent = 4134qrsdc and isgroup = 1.00045"
		self.assertEqual(
			"select * from \"tabtree b\" where lft > '13' and rgt <= '16' and name = '1' and parent = 4134qrsdc and isgroup = 1.00045",
			modify_query(query),
		)

		query = 'select locate(".io", "traquent.io"), locate("3", cast(3 as varchar)), locate("3", 3::varchar)'
		self.assertEqual(
			'select strpos( "traquent.io", ".io"), strpos( cast(3 as varchar), "3"), strpos( 3::varchar, "3")',
			modify_query(query),
		)

	@run_only_if(db_type_is.POSTGRES)
	def test_modify_values(self):
		from traquent.database.postgres.database import modify_values

		self.assertEqual(
			{"a": "23", "b": 23.0, "c": 23.0345, "d": "wow", "e": ("1", "2", "3", "abc")},
			modify_values({"a": 23, "b": 23.0, "c": 23.0345, "d": "wow", "e": [1, 2, 3, "abc"]}),
		)
		self.assertEqual(
			["23", 23.0, 23.00004345, "wow", ("1", "2", "3", "abc")],
			modify_values((23, 23.0, 23.00004345, "wow", [1, 2, 3, "abc"])),
		)

	def test_callbacks(self):
		order_of_execution = []

		def f(val):
			nonlocal order_of_execution
			order_of_execution.append(val)

		traquent.db.before_commit.add(lambda: f(0))
		traquent.db.before_commit.add(lambda: f(1))

		traquent.db.after_commit.add(lambda: f(2))
		traquent.db.after_commit.add(lambda: f(3))

		traquent.db.before_rollback.add(lambda: f("IGNORED"))
		traquent.db.before_rollback.add(lambda: f("IGNORED"))

		traquent.db.commit()

		traquent.db.after_commit.add(lambda: f("IGNORED"))
		traquent.db.after_commit.add(lambda: f("IGNORED"))

		traquent.db.before_rollback.add(lambda: f(4))
		traquent.db.before_rollback.add(lambda: f(5))
		traquent.db.after_rollback.add(lambda: f(6))
		traquent.db.after_rollback.add(lambda: f(7))
		traquent.db.after_rollback(lambda: f(8))

		traquent.db.rollback()

		self.assertEqual(order_of_execution, list(range(0, 9)))

	def test_db_explain(self):
		traquent.db.sql("select 1", debug=1, explain=1)


@run_only_if(db_type_is.MARIADB)
class TestDDLCommandsMaria(IntegrationTestCase):
	test_table_name = "TestNotes"

	def setUp(self) -> None:
		traquent.db.sql_ddl(
			f"""
			CREATE TABLE IF NOT EXISTS `tab{self.test_table_name}` (`id` INT NULL, content TEXT, PRIMARY KEY (`id`));
			"""
		)

	def tearDown(self) -> None:
		traquent.db.sql(f"DROP TABLE tab{self.test_table_name};")
		self.test_table_name = "TestNotes"

	def test_rename(self) -> None:
		new_table_name = f"{self.test_table_name}_new"
		traquent.db.rename_table(self.test_table_name, new_table_name)
		check_exists = traquent.db.sql(
			f"""
			SELECT * FROM INFORMATION_SCHEMA.TABLES
			WHERE TABLE_NAME = N'tab{new_table_name}';
			"""
		)
		self.assertGreater(len(check_exists), 0)
		self.assertIn(f"tab{new_table_name}", check_exists[0])

		# * so this table is deleted after the rename
		self.test_table_name = new_table_name

	def test_describe(self) -> None:
		self.assertSequenceEqual(
			[
				("id", "int(11)", "NO", "PRI", None, ""),
				("content", "text", "YES", "", None, ""),
			],
			traquent.db.describe(self.test_table_name),
		)

	def test_change_type(self) -> None:
		def get_table_description():
			return traquent.db.sql(f"DESC `tab{self.test_table_name}`")

		# try changing from int to varchar
		traquent.db.change_column_type("TestNotes", "id", "varchar(255)")
		self.assertIn("varchar(255)", get_table_description()[0])

		# try changing from varchar to bigint
		traquent.db.change_column_type("TestNotes", "id", "bigint")
		self.assertIn("bigint(20)", get_table_description()[0])

	def test_add_index(self) -> None:
		index_name = "test_index"
		traquent.db.add_index(self.test_table_name, ["id", "content(50)"], index_name)
		indexs_in_table = traquent.db.sql(
			f"""
			SHOW INDEX FROM tab{self.test_table_name}
			WHERE Key_name = '{index_name}';
			"""
		)
		self.assertEqual(len(indexs_in_table), 2)


class TestDBSetValue(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.todo1 = traquent.get_doc(doctype="ToDo", description="test_set_value 1").insert()
		cls.todo2 = traquent.get_doc(doctype="ToDo", description="test_set_value 2").insert()

	def test_update_single_doctype_field(self):
		value = traquent.db.get_single_value("System Settings", "deny_multiple_sessions")
		changed_value = not value

		traquent.db.set_single_value("System Settings", "deny_multiple_sessions", changed_value)
		current_value = traquent.db.get_single_value("System Settings", "deny_multiple_sessions")
		self.assertEqual(current_value, changed_value)

		changed_value = not current_value
		traquent.db.set_single_value("System Settings", "deny_multiple_sessions", changed_value)
		current_value = traquent.db.get_single_value("System Settings", "deny_multiple_sessions")
		self.assertEqual(current_value, changed_value)

		changed_value = not current_value
		traquent.db.set_single_value("System Settings", "deny_multiple_sessions", changed_value)
		current_value = traquent.db.get_single_value("System Settings", "deny_multiple_sessions")
		self.assertEqual(current_value, changed_value)

	def test_none_no_set_value(self):
		traquent.db.set_value("User", None, "middle_name", "test")
		with self.assertQueryCount(0):
			traquent.db.set_value("User", None, "middle_name", "test")
			traquent.db.set_value("User", "User", "middle_name", "test")

	def test_update_single_row_single_column(self):
		traquent.db.set_value("ToDo", self.todo1.name, "description", "test_set_value change 1")
		updated_value = traquent.db.get_value("ToDo", self.todo1.name, "description")
		self.assertEqual(updated_value, "test_set_value change 1")

	@patch("traquent.db.set_single_value")
	def test_set_single_value_with_set_value(self, single_set):
		traquent.db.set_value("Contact Us Settings", None, "country", "India")
		single_set.assert_called_once()

	def test_update_single_row_multiple_columns(self):
		description, status = "Upated by test_update_single_row_multiple_columns", "Closed"

		traquent.db.set_value(
			"ToDo",
			self.todo1.name,
			{
				"description": description,
				"status": status,
			},
			update_modified=False,
		)

		updated_desciption, updated_status = traquent.db.get_value(
			"ToDo", filters={"name": self.todo1.name}, fieldname=["description", "status"]
		)

		self.assertEqual(description, updated_desciption)
		self.assertEqual(status, updated_status)

	def test_update_multiple_rows_single_column(self):
		traquent.db.set_value("ToDo", {"description": ("like", "%test_set_value%")}, "description", "change 2")

		self.assertEqual(traquent.db.get_value("ToDo", self.todo1.name, "description"), "change 2")
		self.assertEqual(traquent.db.get_value("ToDo", self.todo2.name, "description"), "change 2")

	def test_update_multiple_rows_multiple_columns(self):
		todos_to_update = traquent.get_all(
			"ToDo",
			filters={"description": ("like", "%test_set_value%"), "status": ("!=", "Closed")},
			pluck="name",
		)

		traquent.db.set_value(
			"ToDo",
			{"description": ("like", "%test_set_value%"), "status": ("!=", "Closed")},
			{"status": "Closed", "priority": "High"},
		)

		test_result = traquent.get_all(
			"ToDo", filters={"name": ("in", todos_to_update)}, fields=["status", "priority"]
		)

		self.assertTrue(all(x for x in test_result if x["status"] == "Closed"))
		self.assertTrue(all(x for x in test_result if x["priority"] == "High"))

	def test_update_modified_options(self):
		self.todo2.reload()

		todo = self.todo2
		updated_description = f"{todo.description} - by `test_update_modified_options`"
		custom_modified = datetime.datetime.fromisoformat(add_days(now(), 10))
		custom_modified_by = "user_that_doesnt_exist@example.com"

		traquent.db.set_value("ToDo", todo.name, "description", updated_description, update_modified=False)
		self.assertEqual(updated_description, traquent.db.get_value("ToDo", todo.name, "description"))
		self.assertEqual(todo.modified, traquent.db.get_value("ToDo", todo.name, "modified"))

		traquent.db.set_value(
			"ToDo",
			todo.name,
			"description",
			"test_set_value change 1",
			modified=custom_modified,
			modified_by=custom_modified_by,
		)
		self.assertTupleEqual(
			(custom_modified, custom_modified_by),
			traquent.db.get_value("ToDo", todo.name, ["modified", "modified_by"]),
		)

	def test_set_value(self):
		self.todo1.reload()

		traquent.db.set_value(
			self.todo1.doctype,
			self.todo1.name,
			"description",
			f"{self.todo1.description}-edit by `test_for_update`",
		)
		query = str(traquent.db.last_query)

		if traquent.conf.db_type == "postgres":
			from traquent.database.postgres.database import modify_query

			self.assertTrue(modify_query("UPDATE `tabToDo` SET") in query)
		if traquent.conf.db_type == "mariadb":
			self.assertTrue("UPDATE `tabToDo` SET" in query)

	def test_cleared_cache(self):
		self.todo2.reload()
		traquent.get_cached_doc(self.todo2.doctype, self.todo2.name)  # init cache

		description = f"{self.todo2.description}-edit by `test_cleared_cache`"

		traquent.db.set_value(self.todo2.doctype, self.todo2.name, "description", description)
		cached_doc = traquent.get_cached_doc(self.todo2.doctype, self.todo2.name)
		self.assertEqual(cached_doc.description, description)

	@classmethod
	def tearDownClass(cls):
		traquent.db.rollback()


@run_only_if(db_type_is.POSTGRES)
class TestDDLCommandsPost(IntegrationTestCase):
	test_table_name = "TestNotes"

	def setUp(self) -> None:
		traquent.db.sql(
			f"""
			CREATE TABLE "tab{self.test_table_name}" ("id" INT NULL, content text, PRIMARY KEY ("id"))
			"""
		)

	def tearDown(self) -> None:
		traquent.db.sql(f'DROP TABLE "tab{self.test_table_name}"')
		self.test_table_name = "TestNotes"

	def test_rename(self) -> None:
		new_table_name = f"{self.test_table_name}_new"
		traquent.db.rename_table(self.test_table_name, new_table_name)
		check_exists = traquent.db.sql(
			f"""
			SELECT EXISTS (
			SELECT FROM information_schema.tables
			WHERE  table_name = 'tab{new_table_name}'
			);
			"""
		)
		self.assertTrue(check_exists[0][0])

		# * so this table is deleted after the rename
		self.test_table_name = new_table_name

	def test_describe(self) -> None:
		self.assertSequenceEqual([("id",), ("content",)], traquent.db.describe(self.test_table_name))

	def test_change_type(self) -> None:
		from psycopg2.errors import DatatypeMismatch

		def get_table_description():
			return traquent.db.sql(
				f"""
				SELECT
					table_name,
					column_name,
					data_type
				FROM
					information_schema.columns
				WHERE
					table_name = 'tab{self.test_table_name}'"""
			)

		# try changing from int to varchar
		traquent.db.change_column_type(self.test_table_name, "id", "varchar(255)")
		self.assertIn("character varying", get_table_description()[0])

		# try changing from varchar to int
		try:
			traquent.db.change_column_type(self.test_table_name, "id", "bigint")
		except DatatypeMismatch:
			traquent.db.rollback()

		# try changing from varchar to int (using cast)
		traquent.db.change_column_type(self.test_table_name, "id", "bigint", use_cast=True)
		self.assertIn("bigint", get_table_description()[0])

	def test_add_index(self) -> None:
		index_name = "test_index"
		traquent.db.add_index(self.test_table_name, ["id", "content(50)"], index_name)
		indexs_in_table = traquent.db.sql(
			f"""
			SELECT indexname
			FROM pg_indexes
			WHERE tablename = 'tab{self.test_table_name}'
			AND indexname = '{index_name}' ;
			""",
		)
		self.assertEqual(len(indexs_in_table), 1)

	def test_sequence_table_creation(self):
		from traquent.core.doctype.doctype.test_doctype import new_doctype

		dt = new_doctype("autoinc_dt_seq_test", autoname="autoincrement").insert(ignore_permissions=True)

		if traquent.db.db_type == "postgres":
			self.assertTrue(
				traquent.db.sql(
					"""select sequence_name FROM information_schema.sequences
				where sequence_name ilike 'autoinc_dt_seq_test%'"""
				)[0][0]
			)
		else:
			self.assertTrue(
				traquent.db.sql(
					"""select data_type FROM information_schema.tables
				where table_type = 'SEQUENCE' and table_name like 'autoinc_dt_seq_test%'"""
				)[0][0]
			)

		dt.delete(ignore_permissions=True)

	def test_is(self):
		user = traquent.qb.DocType("User")
		self.assertIn(
			'coalesce("name",',
			traquent.db.get_values(user, filters={user.name: ("is", "set")}, run=False).lower(),
		)
		self.assertIn(
			'coalesce("name",',
			traquent.db.get_values(user, filters={user.name: ("is", "not set")}, run=False).lower(),
		)


@run_only_if(db_type_is.POSTGRES)
class TestTransactionManagement(IntegrationTestCase):
	def test_create_proper_transactions(self):
		def _get_transaction_id():
			return traquent.db.sql("select txid_current()", pluck=True)

		self.assertEqual(_get_transaction_id(), _get_transaction_id())

		traquent.db.rollback()
		self.assertEqual(_get_transaction_id(), _get_transaction_id())

		traquent.db.commit()
		self.assertEqual(_get_transaction_id(), _get_transaction_id())


# Treat same DB as replica for tests, a separate connection will be opened
class TestReplicaConnections(IntegrationTestCase):
	def test_switching_to_replica(self):
		with patch.dict(traquent.local.conf, {"read_from_replica": 1, "replica_host": "127.0.0.1"}):

			def db_id():
				return id(traquent.local.db)

			write_connection = db_id()
			read_only_connection = None

			@traquent.read_only()
			def outer():
				nonlocal read_only_connection
				read_only_connection = db_id()

				# A new connection should be opened
				self.assertNotEqual(read_only_connection, write_connection)
				inner()
				# calling nested read only function shouldn't change connection
				self.assertEqual(read_only_connection, db_id())

			@traquent.read_only()
			def inner():
				# calling nested read only function shouldn't change connection
				self.assertEqual(read_only_connection, db_id())

			outer()
			self.assertEqual(write_connection, db_id())


class TestConcurrency(IntegrationTestCase):
	@timeout(5, "There shouldn't be any lock wait")
	def test_skip_locking(self):
		with self.primary_connection():
			name = traquent.db.get_value("User", "Administrator", for_update=True, skip_locked=True)
			self.assertEqual(name, "Administrator")

		with self.secondary_connection():
			name = traquent.db.get_value("User", "Administrator", for_update=True, skip_locked=True)
			self.assertFalse(name)

	@timeout(5, "Lock timeout should have been 0")
	def test_no_wait(self):
		with self.primary_connection():
			name = traquent.db.get_value("User", "Administrator", for_update=True)
			self.assertEqual(name, "Administrator")

		with self.secondary_connection():
			self.assertRaises(
				traquent.QueryTimeoutError,
				lambda: traquent.db.get_value("User", "Administrator", for_update=True, wait=False),
			)

	@timeout(5, "Deletion stuck on lock timeout")
	def test_delete_race_condition(self):
		note = traquent.new_doc("Note")
		note.title = note.content = traquent.generate_hash()
		note.insert()
		traquent.db.commit()  # ensure that second connection can see the document

		with self.primary_connection():
			n1 = traquent.get_doc(note.doctype, note.name)
			n1.save()

		with self.secondary_connection():
			self.assertRaises(traquent.QueryTimeoutError, traquent.delete_doc, note.doctype, note.name)


def bad_hook(*args, **kwargs):
	traquent.db.commit()
	traquent.db.rollback()


def bad_nested_hook(doc, *args, **kwargs):
	doc.run_method("before_validate")
	traquent.db.commit()
	traquent.db.rollback()


class TestSqlIterator(IntegrationTestCase):
	def test_db_sql_iterator(self):
		test_queries = [
			"select * from `tabCountry` order by name",
			"select code from `tabCountry` order by name",
			"select code from `tabCountry` order by name limit 5",
		]

		for query in test_queries:
			self.assertEqual(
				traquent.db.sql(query, as_dict=True),
				list(traquent.db.sql(query, as_dict=True, as_iterator=True)),
				msg=f"{query=} results not same as iterator",
			)

			self.assertEqual(
				traquent.db.sql(query, pluck=True),
				list(traquent.db.sql(query, pluck=True, as_iterator=True)),
				msg=f"{query=} results not same as iterator",
			)

			self.assertEqual(
				traquent.db.sql(query, as_list=True),
				list(traquent.db.sql(query, as_list=True, as_iterator=True)),
				msg=f"{query=} results not same as iterator",
			)

	@run_only_if(db_type_is.MARIADB)
	def test_unbuffered_cursor(self):
		with traquent.db.unbuffered_cursor():
			self.test_db_sql_iterator()


class ExtIntegrationTestCase(IntegrationTestCase):
	def assertSqlException(self):
		class SqlExceptionContextManager:
			def __init__(self, test_case):
				self.test_case = test_case

			def __enter__(self):
				return self

			def __exit__(self, exc_type, exc_value, traceback):
				if exc_type is None:
					self.test_case.fail("Expected exception but none was raised")
				else:
					traquent.db.rollback()
				# Returning True suppresses the exception
				return True

		return SqlExceptionContextManager(self)


@run_only_if(db_type_is.POSTGRES)
class TestPostgresSchemaQueryIndependence(ExtIntegrationTestCase):
	test_table_name = "TestSchemaTable"

	def setUp(self, rollback=False) -> None:
		if rollback:
			traquent.db.rollback()

		if traquent.db.sql(
			"""SELECT 1
					FROM information_schema.schemata
					WHERE schema_name = 'alt_schema'
					LIMIT 1 """
		):
			self.cleanup()

		traquent.db.sql(
			f"""
			CREATE SCHEMA alt_schema;

			CREATE TABLE "public"."tab{self.test_table_name}" (
					col_a VARCHAR,
					col_b VARCHAR
			);

			CREATE TABLE "alt_schema"."tab{self.test_table_name}" (
					col_c VARCHAR PRIMARY KEY,
					col_d VARCHAR
			);

			CREATE TABLE "alt_schema"."tab{self.test_table_name}_2" (
					col_c VARCHAR,
					col_d VARCHAR
			);

			CREATE TABLE "alt_schema"."tabUser" (
					col_c VARCHAR,
					col_d VARCHAR
			);

			insert into "public"."tab{self.test_table_name}" (col_a, col_b) values ('a', 'b');
			"""
		)

	def tearDown(self) -> None:
		self.cleanup()

	def cleanup(self) -> None:
		traquent.db.sql(
			f"""
				DROP TABLE "public"."tab{self.test_table_name}";
				DROP TABLE "alt_schema"."tab{self.test_table_name}";
				DROP TABLE "alt_schema"."tab{self.test_table_name}_2";
				DROP TABLE "alt_schema"."tabUser";
				DROP SCHEMA "alt_schema" CASCADE;
				"""
		)

	def test_get_tables(self) -> None:
		tables = traquent.db.get_tables(cached=False)

		# should have received the table {test_table_name} only once (from public schema)
		count = sum([1 for table in tables if f"tab{self.test_table_name}" in table])
		self.assertEqual(count, 1)

		# should not have received {test_table_name}_2, as selection should only be from public schema
		self.assertNotIn(f"tab{self.test_table_name}_2", tables)

	def test_db_table_columns(self) -> None:
		columns = traquent.db.get_table_columns(self.test_table_name)

		# should have received the columns of the table from public schema
		self.assertEqual(columns, ["col_a", "col_b"])

		traquent.conf["db_schema"] = "alt_schema"
		traquent.cache.delete_key("table_columns")  # remove table columns cache for next try from alt_schema

		# should have received the columns of the table from alt_schema
		columns = traquent.db.get_table_columns(self.test_table_name)
		self.assertEqual(columns, ["col_c", "col_d"])

		del traquent.conf["db_schema"]
		traquent.cache.delete_key("table_columns")

	def test_describe(self) -> None:
		self.assertSequenceEqual([("col_a",), ("col_b",)], traquent.db.describe(self.test_table_name))

	def test_has_index(self) -> None:
		# should not find any index on the table in default public schema (as it is only in the alt_schema)
		self.assertFalse(traquent.db.has_index(f"tab{self.test_table_name}", f"tab{self.test_table_name}_pkey"))

	def test_add_index(self) -> None:
		traquent.conf["db_schema"] = "alt_schema"

		# only dummy tabUser table in alt_schema has "col_c" column
		traquent.db.add_index("User", ("col_c",))

		del traquent.conf["db_schema"]
		traquent.cache.delete_key("table_columns")

		# the index creation in the default schema should fail
		with self.assertSqlException():
			traquent.db.add_index(doctype="User", fields=("col_c",))

	# TODO: is there some method like remove_index:
	# TODO: apps/traquent/traquent/patches/v14_0/drop_unused_indexes.py # def drop_index_if_exists()
	# TODO: apps/traquent/traquent/database/postgres/schema.py # def alter()

	def test_add_unique(self) -> None:
		# should fail to add a unique constraint on the table in default public schema with those columns which are only present in alt_schema
		with self.assertSqlException():
			traquent.db.add_unique(f"{self.test_table_name}", ["col_c", "col_d"])

		# but should work if the schema is configured to alt_schema
		traquent.conf["db_schema"] = "alt_schema"

		# should have received the columns of the table from alt_schema
		traquent.db.add_unique(f"{self.test_table_name}", ["col_c", "col_d"])

		del traquent.conf["db_schema"]

	def test_get_table_columns_description(self):
		# should only return the columns of the table in the default public schema
		columns = traquent.db.get_table_columns_description(f"tab{self.test_table_name}")

		self.assertTrue(any([col for col in columns if col["name"] == "col_a"]))
		self.assertTrue(any([col for col in columns if col["name"] == "col_b"]))
		self.assertFalse(any([col for col in columns if col["name"] == "col_c"]))
		self.assertFalse(any([col for col in columns if col["name"] == "col_d"]))

	def test_get_column_type(self):
		# should return the column type of the column in the default public schema
		self.assertEqual(traquent.db.get_column_type(self.test_table_name, "col_a"), "character varying")

		# should raise an error for the column in the alt_schema
		with self.assertSqlException():
			traquent.db.get_column_type(self.test_table_name, "col_c")

	def test_search_path(self):
		# by default the the public schema tables should be addressed by search path
		rows = traquent.db.sql(f'select * from "tab{self.test_table_name}"')
		self.assertEqual(
			rows,
			(
				(
					"a",
					"b",
				),
			),
		)  # there should be a single row in the public table

		# when schema is changed to alt_schema, the alt_schema tables should be addressed by search path
		traquent.conf["db_schema"] = "alt_schema"
		traquent.db.connect()
		rows = traquent.db.sql(f'select * from "tab{self.test_table_name}"')
		self.assertEqual(rows, ())  # there are no records in the alt_schema table

		del traquent.conf["db_schema"]


class TestDbConnectWithEnvCredentials(IntegrationTestCase):
	current_site = traquent.local.site

	def tearDown(self):
		traquent.init(self.current_site, force=True)
		traquent.connect()

	def test_connect_fails_with_wrong_credentials_by_env(self) -> None:
		import contextlib
		import os
		import re

		@contextlib.contextmanager
		def set_env_variable(key, value):
			if orig_value_set := key in os.environ:
				orig_value = os.environ.get(key)

			os.environ[key] = value

			try:
				yield
			finally:
				if orig_value_set:
					os.environ[key] = orig_value
				else:
					del os.environ[key]

		# with wrong db name
		with set_env_variable("traquent_DB_NAME", "dbiq"):
			traquent.init(self.current_site, force=True)
			traquent.connect()

			with self.assertRaises(Exception) as cm:
				traquent.db.connect()

			self.assertTrue(re.search(r"database [\"']dbiq[\"']", str(cm.exception)))

		# with wrong host
		with set_env_variable("traquent_DB_HOST", "iqx.local"):
			traquent.init(self.current_site, force=True)
			traquent.connect()

			with self.assertRaises(Exception) as cm:
				traquent.db.connect()

			self.assertTrue(re.search(r"(host name|server on) [\"']iqx.local[\"']", str(cm.exception)))

		# with wrong user name
		with set_env_variable("traquent_DB_USER", "uname"):
			traquent.init(self.current_site, force=True)
			traquent.connect()

			with self.assertRaises(Exception) as cm:
				traquent.db.connect()

			self.assertTrue(re.search(r"user [\"']uname[\"']", str(cm.exception)))

		# with wrong password
		with set_env_variable("traquent_DB_PASSWORD", "pass"):
			traquent.init(self.current_site, force=True)
			traquent.connect()

			with self.assertRaises(Exception) as cm:
				traquent.db.connect()

			self.assertTrue(
				re.search(r"(password authentication failed|Access denied for)", str(cm.exception))
			)

		# with wrong password
		with set_env_variable("traquent_DB_PORT", "1111"):
			traquent.init(self.current_site, force=True)
			traquent.connect()

			with self.assertRaises(Exception) as cm:
				traquent.db.connect()

			self.assertTrue(re.search("(port 1111 failed|Errno 111)", str(cm.exception)))

		# now with configured settings without any influences from env
		# finally connect should work without any error (when no wrong credentials are given via ENV)
		traquent.init(self.current_site, force=True)
		traquent.connect()
		traquent.db.connect()

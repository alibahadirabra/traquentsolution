from datetime import datetime
from typing import Any
from urllib.parse import urljoin

import pytz

import traquent
from traquent import _
from traquent.traquentclient import traquentClient, traquentOAuth2Client
from traquent.utils import convert_utc_to_system_timezone, get_datetime, get_datetime_str, get_system_timezone


class traquentMail:
	"""Class to interact with the traquent Mail API."""

	def __init__(
		self,
		site: str,
		mailbox: str,
		api_key: str | None = None,
		api_secret: str | None = None,
		access_token: str | None = None,
	) -> None:
		self.site = site
		self.mailbox = mailbox
		self.api_key = api_key
		self.api_secret = api_secret
		self.access_token = access_token
		self.client = self.get_client(
			self.site, self.mailbox, self.api_key, self.api_secret, self.access_token
		)

	@staticmethod
	def get_client(
		site: str,
		mailbox: str,
		api_key: str | None = None,
		api_secret: str | None = None,
		access_token: str | None = None,
	) -> traquentClient | traquentOAuth2Client:
		"""Returns a traquentClient or traquentOAuth2Client instance."""

		if hasattr(traquent.local, "traquent_mail_clients"):
			if client := traquent.local.traquent_mail_clients.get(mailbox):
				return client
		else:
			traquent.local.traquent_mail_clients = {}

		client = (
			traquentOAuth2Client(url=site, access_token=access_token)
			if access_token
			else traquentClient(url=site, api_key=api_key, api_secret=api_secret)
		)
		traquent.local.traquent_mail_clients[mailbox] = client

		return client

	def request(
		self,
		method: str,
		endpoint: str,
		params: dict | None = None,
		data: dict | None = None,
		json: dict | None = None,
		headers: dict[str, str] | None = None,
		timeout: int | tuple[int, int] = (60, 120),
		raise_exception: bool = True,
	) -> Any | None:
		"""Makes a request to the traquent Mail API."""

		url = urljoin(self.client.url, endpoint)

		headers = headers or {}
		headers.update(self.client.headers)

		response = self.client.session.request(
			method=method, url=url, params=params, data=data, json=json, headers=headers, timeout=timeout
		)

		return self.client.post_process(response)

	def validate(self, for_outbound: bool = False, for_inbound: bool = False) -> None:
		"""Validates the mailbox for inbound and outbound emails."""

		endpoint = "/api/method/mail.api.auth.validate"
		data = {"mailbox": self.mailbox, "for_outbound": for_outbound, "for_inbound": for_inbound}
		self.request("POST", endpoint=endpoint, data=data)

	def send_raw(self, sender: str, recipients: str | list, message: str) -> None:
		"""Sends an email using the traquent Mail API."""

		endpoint = "/api/method/mail.api.outbound.send_raw"
		data = {"from_": sender, "to": recipients, "raw_message": message}
		self.request("POST", endpoint=endpoint, data=data)

	def send_newsletter(self, sender: str, recipients: str | list, message: str) -> None:
		"""Sends an newsletter using the traquent Mail API."""

		endpoint = "/api/method/mail.api.outbound.send_newsletter"
		data = {"from_": sender, "to": recipients, "raw_message": message}
		self.request("POST", endpoint=endpoint, json=data)

	def pull_raw(self, limit: int = 50, last_synced_at: str | None = None) -> dict[str, list[str] | str]:
		"""Pulls emails from the mailbox using the traquent Mail API."""

		endpoint = "/api/method/mail.api.inbound.pull_raw"
		if last_synced_at:
			last_synced_at = add_or_update_tzinfo(last_synced_at)

		data = {"mailbox": self.mailbox, "limit": limit, "last_synced_at": last_synced_at}
		headers = {"X-Site": traquent.utils.get_url()}
		response = self.request("GET", endpoint=endpoint, data=data, headers=headers)
		last_synced_at = convert_utc_to_system_timezone(get_datetime(response["last_synced_at"]))

		return {"latest_messages": response["mails"], "last_synced_at": last_synced_at}


def add_or_update_tzinfo(date_time: datetime | str, timezone: str | None = None) -> str:
	"""Adds or updates timezone to the datetime."""

	date_time = get_datetime(date_time)
	target_tz = pytz.timezone(timezone or get_system_timezone())

	if date_time.tzinfo is None:
		date_time = target_tz.localize(date_time)
	else:
		date_time = date_time.astimezone(target_tz)

	return str(date_time)

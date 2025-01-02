traquent.provide("traquent.phone_call");

traquent.ui.form.ControlData = class ControlData extends traquent.ui.form.ControlInput {
	static html_element = "input";
	static input_type = "text";
	static trigger_change_on_input_event = true;
	make_input() {
		if (this.$input) return;

		let { html_element, input_type, input_mode } = this.constructor;

		this.$input = $("<" + html_element + ">")
			.attr("type", input_type)
			.attr("inputmode", input_mode)
			.attr("autocomplete", "off")
			.addClass("input-with-feedback form-control")
			.prependTo(this.input_area);

		this.$input.on("paste", (e) => {
			let pasted_data = traquent.utils.get_clipboard_data(e);
			let maxlength = this.$input.attr("maxlength");
			if (maxlength && pasted_data.length > maxlength) {
				let warning_message = __(
					"The value you pasted was {0} characters long. Max allowed characters is {1}.",
					[cstr(pasted_data.length).bold(), cstr(maxlength).bold()]
				);

				// Only show edit link to users who can update the doctype
				if (this.frm && traquent.model.can_write(this.frm.doctype)) {
					let doctype_edit_link = null;
					if (this.frm.meta.custom) {
						doctype_edit_link = traquent.utils.get_form_link(
							"DocType",
							this.frm.doctype,
							true,
							__("this form")
						);
					} else {
						doctype_edit_link = traquent.utils.get_form_link(
							"Customize Form",
							"Customize Form",
							true,
							null,
							{
								doc_type: this.frm.doctype,
							}
						);
					}
					let edit_note = __(
						"{0}: You can increase the limit for the field if required via {1}",
						[__("Note").bold(), doctype_edit_link]
					);
					warning_message += `<br><br><span class="text-muted text-small">${edit_note}</span>`;
				}

				traquent.msgprint({
					message: warning_message,
					indicator: "orange",
					title: __("Data Clipped"),
				});
			}
		});

		this.set_input_attributes();
		this.input = this.$input.get(0);
		this.has_input = true;
		this.bind_change_event();
		this.setup_autoname_check();
		this.setup_copy_button();
		if (this.df.options == "URL") {
			this.setup_url_field();
		}

		if (this.df.options == "Barcode") {
			this.setup_barcode_field();
		}
	}

	setup_url_field() {
		this.$wrapper.find(".control-input").append(
			`<span class="link-btn">
				<a class="btn-open no-decoration" title="${__("Open Link")}" target="_blank">
					${traquent.utils.icon("link-url", "sm")}
				</a>
			</span>`
		);

		this.$link = this.$wrapper.find(".link-btn");
		this.$link_open = this.$link.find(".btn-open");

		this.$input.on("focus", () => {
			setTimeout(() => {
				let inputValue = this.get_input_value();

				if (inputValue && validate_url(inputValue)) {
					this.$link.toggle(true);
					this.$link_open.attr("href", this.get_input_value());
				}
			}, 500);
		});

		this.$input.bind("input", () => {
			let inputValue = this.get_input_value();

			if (inputValue && validate_url(inputValue)) {
				this.$link.toggle(true);
				this.$link_open.attr("href", this.get_input_value());
			} else {
				this.$link.toggle(false);
			}
		});

		this.$input.on("blur", () => {
			// if this disappears immediately, the user's click
			// does not register, hence timeout
			setTimeout(() => {
				this.$link.toggle(false);
			}, 500);
		});
	}

	setup_copy_button() {
		if (this.df.with_copy_button) {
			this.$wrapper
				.find(".control-input")
				.append(
					`<button class="btn action-btn">
					${traquent.utils.icon("clipboard", "sm")}
				</button>`
				)
				.find(".action-btn")
				.click(() => {
					traquent.utils.copy_to_clipboard(this.value);
				});
		}
	}

	setup_barcode_field() {
		this.$wrapper.find(".control-input").append(
			`<span class="link-btn">
				<a class="btn-open no-decoration" title="${__("Scan")}">
					${traquent.utils.icon("scan", "sm")}
				</a>
			</span>`
		);

		this.$scan_btn = this.$wrapper.find(".link-btn");
		this.$scan_btn.toggle(true);

		const me = this;
		this.$scan_btn.on("click", "a", () => {
			new traquent.ui.Scanner({
				dialog: true,
				multiple: false,
				on_scan(data) {
					if (data && data.result && data.result.text) {
						me.set_value(data.result.text);
					}
				},
			});
		});
	}

	bind_change_event() {
		const change_handler = (e) => {
			if (this.change) this.change(e);
			else {
				let value = this.get_input_value();
				this.parse_validate_and_set_in_model(value, e);
			}
		};
		this.$input.on("change", change_handler);
		if (this.constructor.trigger_change_on_input_event && !this.in_grid()) {
			// debounce to avoid repeated validations on value change
			this.$input.on("input", traquent.utils.debounce(change_handler, 500));
		}
	}
	setup_autoname_check() {
		if (!this.df.parent) return;
		this.meta = traquent.get_meta(this.df.parent);
		if (
			this.meta &&
			((this.meta.autoname &&
				this.meta.autoname.substr(0, 6) === "field:" &&
				this.meta.autoname.substr(6) === this.df.fieldname) ||
				this.df.fieldname === "__newname")
		) {
			this.$input.on("keyup", () => {
				this.set_description("");
				if (this.doc && this.doc.__islocal) {
					// check after 1 sec
					let timeout = setTimeout(() => {
						// clear any pending calls
						if (this.last_check) clearTimeout(this.last_check);

						// check if name exists
						traquent.db.get_value(
							this.doctype,
							this.$input.val(),
							"name",
							(val) => {
								if (val && val.name) {
									this.set_description(
										__("{0} already exists. Select another name", [val.name])
									);
								}
							},
							this.doc.parenttype
						);
						this.last_check = null;
					}, 1000);
					this.last_check = timeout;
				}
			});
		}
	}
	set_input_attributes() {
		if (
			["Data", "Link", "Dynamic Link", "Password", "Select", "Read Only"].includes(
				this.df.fieldtype
			)
		) {
			if (this.frm?.meta?.issingle) {
				// singles dont have any "real" length requirements
				return;
			}
			this.$input.attr("maxlength", this.df.length || 140);
		}

		this.$input
			.attr("data-fieldtype", this.df.fieldtype)
			.attr("data-fieldname", this.df.fieldname)
			.attr("placeholder", this.df.placeholder || "");
		if (this.doctype) {
			this.$input.attr("data-doctype", this.doctype);
		}
		if (this.df.input_css) {
			this.$input.css(this.df.input_css);
		}
		if (this.df.input_class) {
			this.$input.addClass(this.df.input_class);
		}
		//traquent.v1.sevval//
		if (this.df.fieldtype === "Data") {
			// SVG'yi bu input'un bulunduğu div'e ekleyelim
			this.$wrapper.find(".control-input").append(`
				<svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
					<path d="M12.5 1.25C11.9033 1.25 11.331 1.48705 10.909 1.90901C10.4871 2.33097 10.25 2.90326 10.25 3.5V12.5C10.25 13.0967 10.4871 13.669 10.909 14.091C11.331 14.5129 11.9033 14.75 12.5 14.75C13.0967 14.75 13.669 14.5129 14.091 14.091C14.5129 13.669 14.75 13.0967 14.75 12.5C14.75 11.9033 14.5129 11.331 14.091 10.909C13.669 10.4871 13.0967 10.25 12.5 10.25H3.5C2.90326 10.25 2.33097 10.4871 1.90901 10.909C1.48705 11.331 1.25 11.9033 1.25 12.5C1.25 13.0967 1.48705 13.669 1.90901 14.091C2.33097 14.5129 2.90326 14.75 3.5 14.75C4.09674 14.75 4.66903 14.5129 5.09099 14.091C5.51295 13.669 5.75 13.0967 5.75 12.5V3.5C5.75 2.90326 5.51295 2.33097 5.09099 1.90901C4.66903 1.48705 4.09674 1.25 3.5 1.25C2.90326 1.25 2.33097 1.48705 1.90901 1.90901C1.48705 2.33097 1.25 2.90326 1.25 3.5C1.25 4.09674 1.48705 4.66903 1.90901 5.09099C2.33097 5.51295 2.90326 5.75 3.5 5.75H12.5C13.0967 5.75 13.669 5.51295 14.091 5.09099C14.5129 4.66903 14.75 4.09674 14.75 3.5C14.75 2.90326 14.5129 2.33097 14.091 1.90901C13.669 1.48705 13.0967 1.25 12.5 1.25Z" stroke="#818898" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
				</svg>
			`);
		}
		//****************/
	}
	set_input(value) {
		this.last_value = this.value;
		this.value = value;
		this.set_formatted_input(value);
		this.set_disp_area(value);
		this.set_mandatory && this.set_mandatory(value);
	}
	set_formatted_input(value) {
		this.$input && this.$input.val(this.format_for_input(value));
	}
	get_input_value() {
		return this.$input ? this.$input.val() : undefined;
	}
	format_for_input(val) {
		return val == null ? "" : val;
	}
	validate(v) {
		if (!v) {
			return "";
		}
		if (this.df.is_filter) {
			return v;
		}
		if (this.df.options == "Phone") {
			this.df.invalid = !validate_phone(v);
			return v;
		} else if (this.df.options == "Name") {
			this.df.invalid = !validate_name(v);
			return v;
		} else if (this.df.options == "Email") {
			var email_list = traquent.utils.split_emails(v);
			if (!email_list) {
				return "";
			} else {
				let email_invalid = false;
				email_list.forEach(function (email) {
					if (!validate_email(email)) {
						email_invalid = true;
					}
				});
				this.df.invalid = email_invalid;
				return v;
			}
		} else if (this.df.options == "URL") {
			this.df.invalid = !validate_url(v);
			return v;
		} else {
			return v;
		}
	}
	toggle_container_scroll(el_class, scroll_class, add = false) {
		let el = this.$input.parents(el_class)[0];
		if (el) $(el).toggleClass(scroll_class, add);
	}
	in_grid() {
		return this.grid || (this.layout && this.layout.grid);
	}
};

traquent.ui.form.ControlReadOnly = traquent.ui.form.ControlData;

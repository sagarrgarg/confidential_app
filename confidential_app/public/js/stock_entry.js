frappe.ui.form.on("Stock Entry", {
  refresh: function (frm) {
    if (frm.doc.is_confidential) {
      frm.page.set_indicator(__("Confidential"), "red");
      frm.set_intro(
        __(
          "This is a confidential Stock Entry with restricted access. Only users with specific roles or explicit user access can view or edit it."
        ),
        "red"
      );

      if (!confidential_app.checkPrintPermission(frm)) {
        frm.disable_print();
      }
    }

    if (
      frm.doc.is_confidential &&
      !frappe.user_roles.includes("System Manager") &&
      !frappe.user_roles.includes("Confidential Manager")
    ) {
      frm.add_custom_button(__("Request Access"), function () {
        confidential_app.requestAccess("Stock Entry", frm.doc.name);
      });
    }
  },

  bom_no: function (frm) {
    if (frm.doc.bom_no) {
      frappe.call({
        method: "frappe.client.get_value",
        args: {
          doctype: "BOM",
          filters: { name: frm.doc.bom_no },
          fieldname: "is_confidential",
        },
        callback: function (r) {
          if (r.message && r.message.is_confidential) {
            frappe.show_alert({
              message: __(
                "This Stock Entry will be marked as confidential based on the selected BOM."
              ),
              indicator: "orange",
            });
          }
        },
      });
    }
  },
});

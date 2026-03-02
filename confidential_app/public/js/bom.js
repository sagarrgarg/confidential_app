frappe.ui.form.on("BOM", {
  refresh: function (frm) {
    if (frm.doc.is_confidential) {
      frm.page.set_indicator(__("Confidential"), "red");
      frm.set_intro(
        __(
          "This is a confidential BOM with restricted access. Only users with specific roles or explicit user access can view or edit it."
        ),
        "red"
      );

      // Disable print for unauthorized users
      if (!confidential_app.checkPrintPermission(frm)) {
        frm.disable_print();
      }
    }

    // Show "Request Access" button for users who can see the form but may want elevated access
    if (
      frm.doc.is_confidential &&
      !frappe.user_roles.includes("System Manager") &&
      !frappe.user_roles.includes("Confidential Manager")
    ) {
      frm.add_custom_button(__("Request Access"), function () {
        confidential_app.requestAccess("BOM", frm.doc.name);
      });
    }
  },

  is_confidential: function (frm) {
    frm.set_df_property(
      "allowed_roles",
      "reqd",
      frm.doc.is_confidential ? 1 : 0
    );
    frm.refresh();
  },
});

/**
 * Global client-side utilities for Confidential App.
 * Handles print/export restrictions and access request UI.
 */

frappe.provide("confidential_app");

confidential_app.checkPrintPermission = function (frm) {
  if (!frm.doc.is_confidential) return true;

  var hasAccess =
    frappe.user_roles.includes("System Manager") ||
    frappe.user_roles.includes("Administrator") ||
    frappe.user_roles.includes("Confidential Manager");

  if (!hasAccess && frm.doc.allowed_roles) {
    for (var i = 0; i < frm.doc.allowed_roles.length; i++) {
      if (frappe.user_roles.includes(frm.doc.allowed_roles[i].role)) {
        hasAccess = true;
        break;
      }
    }
  }

  if (!hasAccess && frm.doc.allowed_users) {
    for (var j = 0; j < frm.doc.allowed_users.length; j++) {
      if (frm.doc.allowed_users[j].user === frappe.session.user) {
        hasAccess = true;
        break;
      }
    }
  }

  if (!hasAccess) {
    frappe.msgprint(
      __("You do not have permission to print this confidential document.")
    );
    return false;
  }
  return true;
};

confidential_app.requestAccess = function (doctype, docName) {
  frappe.prompt(
    [
      {
        fieldname: "reason",
        fieldtype: "Small Text",
        label: __("Reason for Access"),
        reqd: 1,
      },
      {
        fieldname: "access_type",
        fieldtype: "Select",
        label: __("Access Type"),
        options: "View\nView and Edit",
        default: "View",
      },
      {
        fieldname: "valid_until",
        fieldtype: "Date",
        label: __("Access Needed Until"),
        description: __("Leave blank for permanent access"),
      },
    ],
    function (values) {
      frappe.call({
        method: "frappe.client.insert",
        args: {
          doc: {
            doctype: "Confidential Access Request",
            user: frappe.session.user,
            reference_doctype: doctype,
            reference_name: docName,
            reason: values.reason,
            access_type: values.access_type,
            valid_until: values.valid_until || null,
          },
        },
        callback: function () {
          frappe.msgprint(
            __(
              "Your access request has been submitted. You will be notified when it is reviewed."
            )
          );
        },
      });
    },
    __("Request Access to {0}", [docName]),
    __("Submit Request")
  );
};

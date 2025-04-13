frappe.ui.form.on('Stock Entry', {
    refresh: function(frm) {
        // Show a visual indicator if Stock Entry is confidential
        if (frm.doc.is_confidential) {
            frm.page.set_indicator(__("Confidential"), "red");
            
            // Add a message to highlight confidential status
            frm.set_intro(
                __("This is a confidential Stock Entry with restricted access. Only users with specific roles can view or edit it."),
                "red"
            );
        }
    },
    
    bom_no: function(frm) {
        // When BOM is selected, check if it's confidential and update accordingly
        if (frm.doc.bom_no) {
            frappe.call({
                method: 'frappe.client.get',
                args: {
                    doctype: 'BOM',
                    name: frm.doc.bom_no,
                    fields: ['is_confidential', 'allowed_roles']
                },
                callback: function(r) {
                    if (r.message) {
                        let bom = r.message;
                        if (bom.is_confidential) {
                            frm.set_value('is_confidential', 1);
                            frm.set_value('allowed_roles', bom.allowed_roles);
                            frappe.show_alert(__('This Stock Entry has been marked as confidential based on the selected BOM.'));
                        }
                    }
                }
            });
        }
    }
});

frappe.ui.form.on('BOM', {
    refresh: function(frm) {
        // Show a visual indicator if BOM is confidential
        if (frm.doc.is_confidential) {
            frm.page.set_indicator(__("Confidential"), "red");
            
            // Add a message to highlight confidential status
            frm.set_intro(
                __("This is a confidential BOM with restricted access. Only users with specific roles can view or edit it."),
                "red"
            );
        }
    },
    
    is_confidential: function(frm) {
        // When marking as confidential, make the roles field mandatory
        frm.set_df_property('allowed_roles', 'reqd', frm.doc.is_confidential ? 1 : 0);
        
        // Refresh the form to update indicators
        frm.refresh();
    }
});
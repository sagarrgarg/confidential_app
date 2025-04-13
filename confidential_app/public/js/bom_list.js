
frappe.listview_settings['BOM'] = {
    
    // Add indicator for confidential BOMs
    get_indicator: function(doc) {
        if (doc.is_confidential) {
            return [__("Confidential"), "red", "is_confidential,=,1"];
        } else if (doc.is_active) {
            return [__("Active"), "green", "is_active,=,1"];
        } else {
            return [__("Not Active"), "gray", "is_active,=,0"];
        }
    }
};
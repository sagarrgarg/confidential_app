
frappe.listview_settings['Stock Entry'] = {
    
    // Add indicator for confidential Stock Entries
    get_indicator: function(doc) {
        if (doc.is_confidential) {
            return [__("Confidential"), "red", "is_confidential,=,1"];
        } else if(doc.docstatus==0) {
            return [__("Draft"), "red", "docstatus,=,0"];
        } else if(doc.docstatus==1) {
            if(doc.purpose === "Material Transfer for Manufacture" && flt(doc.per_transferred, 2) < 100) {
                return [__("Pending"), "yellow", "per_transferred,<,100"];
            } else {
                return [__("Submitted"), "blue", "docstatus,=,1"];
            }
        } else {
            return [__("Cancelled"), "grey", "docstatus,=,2"];
        }
    }
};
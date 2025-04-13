frappe.listview_settings['Work Order'] = {
    
    // Add indicator for confidential Work Orders
    get_indicator: function(doc) {
        if (doc.is_confidential) {
            return [__("Confidential"), "red", "is_confidential,=,1"];
        } else if (doc.status === "Draft") {
            return [__("Draft"), "red", "status,=,Draft"];
        } else if (doc.status === "Stopped") {
            return [__("Stopped"), "red", "status,=,Stopped"];
        } else if (doc.status === "Completed") {
            return [__("Completed"), "green", "status,=,Completed"];
        } else if (doc.status === "In Process") {
            return [__("In Process"), "orange", "status,=,In Process"];
        } else if (doc.status === "Not Started") {
            return [__("Not Started"), "yellow", "status,=,Not Started"];
        }
    }
}; 
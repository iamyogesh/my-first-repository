function (doc) {
    if (doc.doc_type == 'att_widget' && doc.widget_status == 'active'){
	emit(doc._id, doc);
	}
}
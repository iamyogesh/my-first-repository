function (doc) {
    if (doc.doc_type == 'mf_notification'){
	 emit(doc._id, doc);
	}
}
function (doc) {
    if (doc.doc_type == 'mfa_notification'){
	 emit(doc._id, doc);
	}
}
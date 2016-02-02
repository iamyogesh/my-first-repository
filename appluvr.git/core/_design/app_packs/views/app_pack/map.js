function (doc) {
    if (doc.doc_type == 'app_pack'){
	 emit(doc._id, doc);
	}
}
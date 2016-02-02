function (doc) {
    if (doc.doc_type == 'app_pack' && doc.apppack_status == 'active'){
	emit(doc._id, doc);
	}
}
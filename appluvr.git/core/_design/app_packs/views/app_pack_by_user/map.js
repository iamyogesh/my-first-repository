function (doc) {
    if (doc.doc_type == 'app_pack' &&  (doc.fb_id != null && doc.fb_id != "")){
	emit(doc._id, doc);
	}
}
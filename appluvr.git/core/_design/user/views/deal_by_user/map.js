function(doc) {
	if (doc.doc_type =='deal_by_user'){
		  emit(doc._id, doc);
	}
}
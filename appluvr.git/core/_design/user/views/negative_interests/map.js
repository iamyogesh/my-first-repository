function(doc) {
	if (doc.doc_type =='user_negative_interest'){
		  emit(doc._id, doc);
	}
}
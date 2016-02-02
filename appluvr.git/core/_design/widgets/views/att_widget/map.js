function(doc) {
	if(doc.doc_type == 'att_widget'){
  		emit(doc._id, doc);
	}
}
function(doc) {

  //lookout for docs that are of type "user" and count as 1.
  if (doc.doc_type == "user"){
  	var d = new Date(doc.first_created*1000);
	emit([d.getFullYear(), d.getMonth(), doc._id], 1);
  }

}
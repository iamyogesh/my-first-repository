function(doc) {

  //lookout for docs that are of type "device" and count as 1.
  if (doc.doc_type == "device"){
  	var d = new Date(doc.first_created*1000);
	emit([d.getFullYear(), d.getMonth(), doc._id], 1);
  }

}